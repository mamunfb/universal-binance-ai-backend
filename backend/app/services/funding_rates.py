from __future__ import annotations

import math
import sqlite3
from decimal import Decimal, InvalidOperation
import psycopg
from psycopg.rows import dict_row
from datetime import datetime, timezone
from pathlib import Path
from app.services.collector_leases import assert_collector_lease_owned
from typing import Any


class FundingRateStore:
    """Idempotent local storage for Binance USD-M funding events."""

    def __init__(self, database_path: str, database_url: str = "") -> None:
        self.database_path = database_path
        self.database_url = database_url.strip()
        if self.database_url:
            return
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(database_path) as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS historical_funding_rates (
                    market TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    funding_time_ms INTEGER NOT NULL,
                    funding_rate REAL NOT NULL,
                    mark_price REAL,
                    source TEXT NOT NULL,
                    collected_at TEXT NOT NULL,
                    PRIMARY KEY (market, symbol, funding_time_ms)
                )
            """)
            connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_funding_history_lookup
                ON historical_funding_rates(market, symbol, funding_time_ms)
            """)

    def _connect_postgres(self):
        return psycopg.connect(self.database_url, sslmode=("disable" if "sslmode=disable" in self.database_url else "require"), connect_timeout=15, row_factory=dict_row)

    @staticmethod
    def _finite(value: Any, field: str) -> float:
        try:
            if isinstance(value, bool):
                raise ValueError
            number = float(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"Invalid funding {field}") from exc
        if not math.isfinite(number):
            raise ValueError(f"Invalid funding {field}")
        return number

    @staticmethod
    def _integer(value: Any, field: str) -> int:
        if isinstance(value, bool):
            raise ValueError(f"Invalid {field}")
        try:
            number = Decimal(str(value))
            if not number.is_finite() or number != number.to_integral_value():
                raise ValueError
            return int(number)
        except (InvalidOperation, TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"Invalid {field}") from exc

    @classmethod
    def _normalize(cls, row: Any) -> tuple[int, float, float | None]:
        if not isinstance(row, dict):
            raise ValueError("Malformed Binance funding row")
        try:
            funding_time = cls._integer(row["fundingTime"], "funding timestamp")
        except KeyError as exc:
            raise ValueError("Invalid funding timestamp") from exc
        rate = cls._finite(row.get("fundingRate"), "rate")
        mark_raw = row.get("markPrice")
        mark = None if mark_raw in (None, "") else cls._finite(mark_raw, "mark price")
        if funding_time < 0 or (mark is not None and mark <= 0):
            raise ValueError("Invalid funding timestamp or mark price")
        return funding_time, rate, mark

    def save(
        self, market: str, symbol: str, rows: list[Any],
        source: str = "Binance USD-M public REST API",
        lease_owner_token: str | None = None,
    ) -> dict[str, Any]:
        market = market.upper()
        symbol = symbol.upper().strip()
        if market != "USD_M":
            raise ValueError("Funding history storage currently supports USD_M only")
        if not symbol:
            raise ValueError("symbol must not be empty")
        if not isinstance(rows, list) or not 1 <= len(rows) <= 1000:
            raise ValueError("rows must contain between 1 and 1000 funding events")
        for row in rows:
            if not isinstance(row, dict) or str(row.get("symbol", "")).upper() != symbol:
                raise ValueError("Funding event symbol does not match requested symbol")
        normalized = [self._normalize(row) for row in rows]
        if len({row[0] for row in normalized}) != len(normalized):
            raise ValueError("Duplicate funding timestamps in provider response")
        normalized.sort(key=lambda row: row[0])
        now = datetime.now(timezone.utc).isoformat()
        values = [(market, symbol, timestamp, rate, mark, source, now)
                  for timestamp, rate, mark in normalized]
        if self.database_url:
            with self._connect_postgres() as connection:
                if lease_owner_token is not None:
                    assert_collector_lease_owned(connection, "derivatives-history:all", lease_owner_token)
                connection.cursor().executemany("""
                    INSERT INTO public.historical_funding_rates (
                        market, symbol, funding_time_ms, funding_rate, mark_price, source, collected_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT(market, symbol, funding_time_ms) DO UPDATE SET
                        funding_rate=excluded.funding_rate, mark_price=excluded.mark_price,
                        source=excluded.source, collected_at=excluded.collected_at
                """, values)
                total = connection.execute("""
                    SELECT COUNT(*) AS count FROM public.historical_funding_rates
                    WHERE market=%s AND symbol=%s
                """, (market, symbol)).fetchone()["count"]
            storage = "POSTGRESQL"
        else:
            if lease_owner_token is not None:
                raise RuntimeError("Distributed collector lease writes require PostgreSQL storage")
            with sqlite3.connect(self.database_path) as connection:
                connection.executemany("""
                    INSERT INTO historical_funding_rates (
                        market, symbol, funding_time_ms, funding_rate, mark_price, source, collected_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(market, symbol, funding_time_ms) DO UPDATE SET
                        funding_rate=excluded.funding_rate, mark_price=excluded.mark_price,
                        source=excluded.source, collected_at=excluded.collected_at
                """, values)
                total = connection.execute("""
                    SELECT COUNT(*) FROM historical_funding_rates
                    WHERE market=? AND symbol=?
                """, (market, symbol)).fetchone()[0]
            storage = "SQLITE_IDEMPOTENT"
        return {
            "status": "COMPLETED", "market": market, "symbol": symbol,
            "received_count": len(rows), "stored_count": len(normalized),
            "total_stored_count": int(total),
            "first_funding_time_ms": normalized[0][0],
            "last_funding_time_ms": normalized[-1][0],
            "collected_at": now, "source": source, "storage": storage,
        }

    def history(
        self, market: str, symbol: str,
        start_time_ms: int | None = None, end_time_ms: int | None = None,
        limit: int = 1000,
    ) -> dict[str, Any]:
        market = market.upper()
        symbol = symbol.upper().strip()
        if market != "USD_M":
            raise ValueError("Funding history storage currently supports USD_M only")
        if not symbol:
            raise ValueError("symbol must not be empty")
        if not 1 <= limit <= 5000:
            raise ValueError("limit must be between 1 and 5000")
        if start_time_ms is not None and start_time_ms < 0:
            raise ValueError("start_time_ms must be non-negative")
        if end_time_ms is not None and end_time_ms < 0:
            raise ValueError("end_time_ms must be non-negative")
        if start_time_ms is not None and end_time_ms is not None and end_time_ms < start_time_ms:
            raise ValueError("end_time_ms must be >= start_time_ms")
        clauses = ["market=?", "symbol=?"]
        params: list[Any] = [market, symbol]
        if start_time_ms is not None:
            clauses.append("funding_time_ms>=?")
            params.append(start_time_ms)
        if end_time_ms is not None:
            clauses.append("funding_time_ms<=?")
            params.append(end_time_ms)
        params.append(limit)
        if self.database_url:
            pg_clauses = ["market=%s", "symbol=%s"]
            pg_params: list[Any] = [market, symbol]
            if start_time_ms is not None:
                pg_clauses.append("funding_time_ms>=%s")
                pg_params.append(start_time_ms)
            if end_time_ms is not None:
                pg_clauses.append("funding_time_ms<=%s")
                pg_params.append(end_time_ms)
            pg_params.append(limit)
            with self._connect_postgres() as connection:
                rows = connection.execute(f"""
                    SELECT funding_time_ms, funding_rate, mark_price, source, collected_at
                    FROM public.historical_funding_rates WHERE {' AND '.join(pg_clauses)}
                    ORDER BY funding_time_ms DESC LIMIT %s
                """, pg_params).fetchall()
            source_label = "Neon PostgreSQL funding history"
        else:
            with sqlite3.connect(self.database_path) as connection:
                connection.row_factory = sqlite3.Row
                rows = connection.execute(f"""
                    SELECT funding_time_ms, funding_rate, mark_price, source, collected_at
                    FROM historical_funding_rates WHERE {' AND '.join(clauses)}
                    ORDER BY funding_time_ms DESC LIMIT ?
                """, params).fetchall()
            source_label = "Local SQLite funding history"
        events = [dict(row) for row in reversed(rows)]
        gaps = []
        for previous, current in zip(events, events[1:]):
            delta = current["funding_time_ms"] - previous["funding_time_ms"]
            if delta > 0:
                gaps.append({"from_funding_time_ms": previous["funding_time_ms"],
                             "to_funding_time_ms": current["funding_time_ms"],
                             "observed_gap_ms": delta})
        return {
            "status": "COMPLETED" if events else "NO_STORED_DATA",
            "market": market, "symbol": symbol, "returned_count": len(events),
            "events": events,
            "coverage": {
                "first_funding_time_ms": events[0]["funding_time_ms"] if events else None,
                "last_funding_time_ms": events[-1]["funding_time_ms"] if events else None,
                "observed_event_gaps": gaps,
                "expected_schedule_verified": False,
                "note": "Funding intervals can vary by contract and over time. Observed time deltas are reported only; they are not classified as missing events.",
            },
            "source": f"{source_label}; original source retained per event.",
        }
