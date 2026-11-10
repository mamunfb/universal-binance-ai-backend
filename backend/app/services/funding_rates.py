from __future__ import annotations

import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class FundingRateStore:
    """Idempotent local storage for Binance USD-M funding events."""

    def __init__(self, database_path: str) -> None:
        self.database_path = database_path
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

    @staticmethod
    def _finite(value: Any, field: str) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"Invalid funding {field}") from exc
        if not math.isfinite(number):
            raise ValueError(f"Invalid funding {field}")
        return number

    @classmethod
    def _normalize(cls, row: Any) -> tuple[int, float, float | None]:
        if not isinstance(row, dict):
            raise ValueError("Malformed Binance funding row")
        try:
            funding_time = int(row["fundingTime"])
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
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
        with sqlite3.connect(self.database_path) as connection:
            connection.executemany("""
                INSERT INTO historical_funding_rates (
                    market, symbol, funding_time_ms, funding_rate, mark_price, source, collected_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(market, symbol, funding_time_ms) DO UPDATE SET
                    funding_rate=excluded.funding_rate,
                    mark_price=excluded.mark_price,
                    source=excluded.source,
                    collected_at=excluded.collected_at
            """, values)
            total = connection.execute("""
                SELECT COUNT(*) FROM historical_funding_rates
                WHERE market=? AND symbol=?
            """, (market, symbol)).fetchone()[0]
        return {
            "status": "COMPLETED", "market": market, "symbol": symbol,
            "received_count": len(rows), "stored_count": len(normalized),
            "total_stored_count": int(total),
            "first_funding_time_ms": normalized[0][0],
            "last_funding_time_ms": normalized[-1][0],
            "collected_at": now, "source": source, "storage": "SQLITE_IDEMPOTENT",
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
        with sqlite3.connect(self.database_path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(f"""
                SELECT funding_time_ms, funding_rate, mark_price, source, collected_at
                FROM historical_funding_rates WHERE {' AND '.join(clauses)}
                ORDER BY funding_time_ms DESC LIMIT ?
            """, params).fetchall()
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
            "source": "Local SQLite funding history; original source retained per event.",
        }
