from __future__ import annotations

import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


OPEN_INTEREST_PERIODS = {"5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d"}


class OpenInterestStore:
    """Idempotent SQLite storage for Binance USD-M open-interest statistics."""

    def __init__(self, database_path: str) -> None:
        self.database_path = database_path
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(database_path) as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS historical_open_interest (
                    market TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    period TEXT NOT NULL,
                    timestamp_ms INTEGER NOT NULL,
                    sum_open_interest REAL NOT NULL,
                    sum_open_interest_value REAL NOT NULL,
                    cmc_circulating_supply REAL,
                    source TEXT NOT NULL,
                    collected_at TEXT NOT NULL,
                    PRIMARY KEY (market, symbol, period, timestamp_ms)
                )
            """)
            connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_open_interest_lookup
                ON historical_open_interest(market, symbol, period, timestamp_ms)
            """)

    @staticmethod
    def _finite(value: Any, field: str) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"Invalid open interest {field}") from exc
        if not math.isfinite(number):
            raise ValueError(f"Invalid open interest {field}")
        return number

    @classmethod
    def _normalize(cls, row: Any) -> tuple[int, float, float, float | None]:
        if not isinstance(row, dict):
            raise ValueError("Malformed Binance open-interest row")
        try:
            timestamp = int(row["timestamp"])
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise ValueError("Invalid open-interest timestamp") from exc
        amount = cls._finite(row.get("sumOpenInterest"), "amount")
        value = cls._finite(row.get("sumOpenInterestValue"), "value")
        supply_raw = row.get("CMCCirculatingSupply")
        supply = None if supply_raw in (None, "") else cls._finite(supply_raw, "circulating supply")
        if timestamp < 0 or amount < 0 or value < 0 or (supply is not None and supply < 0):
            raise ValueError("Open-interest timestamp and metrics must be non-negative")
        return timestamp, amount, value, supply

    def save(
        self, market: str, symbol: str, period: str, rows: list[Any],
        source: str = "Binance USD-M public REST API",
    ) -> dict[str, Any]:
        market = market.upper()
        symbol = symbol.upper().strip()
        if market != "USD_M":
            raise ValueError("Open-interest history storage currently supports USD_M only")
        if not symbol:
            raise ValueError("symbol must not be empty")
        if period not in OPEN_INTEREST_PERIODS:
            raise ValueError("Unsupported open-interest period")
        if not isinstance(rows, list) or not 1 <= len(rows) <= 500:
            raise ValueError("rows must contain between 1 and 500 open-interest records")
        for row in rows:
            if not isinstance(row, dict) or str(row.get("symbol", "")).upper() != symbol:
                raise ValueError("Open-interest event symbol does not match requested symbol")
        normalized = [self._normalize(row) for row in rows]
        if len({row[0] for row in normalized}) != len(normalized):
            raise ValueError("Duplicate open-interest timestamps in provider response")
        normalized.sort(key=lambda row: row[0])
        now = datetime.now(timezone.utc).isoformat()
        values = [(market, symbol, period, timestamp, amount, value, supply, source, now)
                  for timestamp, amount, value, supply in normalized]
        with sqlite3.connect(self.database_path) as connection:
            connection.executemany("""
                INSERT INTO historical_open_interest (
                    market, symbol, period, timestamp_ms, sum_open_interest,
                    sum_open_interest_value, cmc_circulating_supply, source, collected_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(market, symbol, period, timestamp_ms) DO UPDATE SET
                    sum_open_interest=excluded.sum_open_interest,
                    sum_open_interest_value=excluded.sum_open_interest_value,
                    cmc_circulating_supply=excluded.cmc_circulating_supply,
                    source=excluded.source,
                    collected_at=excluded.collected_at
            """, values)
            total = connection.execute("""
                SELECT COUNT(*) FROM historical_open_interest
                WHERE market=? AND symbol=? AND period=?
            """, (market, symbol, period)).fetchone()[0]
        return {
            "status": "COMPLETED", "market": market, "symbol": symbol, "period": period,
            "received_count": len(rows), "stored_count": len(normalized),
            "total_stored_count": int(total),
            "first_timestamp_ms": normalized[0][0], "last_timestamp_ms": normalized[-1][0],
            "collected_at": now, "source": source, "storage": "SQLITE_IDEMPOTENT",
        }

    def history(
        self, market: str, symbol: str, period: str = "1h",
        start_time_ms: int | None = None, end_time_ms: int | None = None,
        limit: int = 500,
    ) -> dict[str, Any]:
        market = market.upper()
        symbol = symbol.upper().strip()
        if market != "USD_M":
            raise ValueError("Open-interest history storage currently supports USD_M only")
        if not symbol:
            raise ValueError("symbol must not be empty")
        if period not in OPEN_INTEREST_PERIODS:
            raise ValueError("Unsupported open-interest period")
        if not 1 <= limit <= 5000:
            raise ValueError("limit must be between 1 and 5000")
        if start_time_ms is not None and start_time_ms < 0:
            raise ValueError("start_time_ms must be non-negative")
        if end_time_ms is not None and end_time_ms < 0:
            raise ValueError("end_time_ms must be non-negative")
        if start_time_ms is not None and end_time_ms is not None and end_time_ms < start_time_ms:
            raise ValueError("end_time_ms must be >= start_time_ms")
        clauses = ["market=?", "symbol=?", "period=?"]
        params: list[Any] = [market, symbol, period]
        if start_time_ms is not None:
            clauses.append("timestamp_ms>=?")
            params.append(start_time_ms)
        if end_time_ms is not None:
            clauses.append("timestamp_ms<=?")
            params.append(end_time_ms)
        params.append(limit)
        with sqlite3.connect(self.database_path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(f"""
                SELECT timestamp_ms, sum_open_interest, sum_open_interest_value,
                       cmc_circulating_supply, source, collected_at
                FROM historical_open_interest WHERE {' AND '.join(clauses)}
                ORDER BY timestamp_ms DESC LIMIT ?
            """, params).fetchall()
        records = [dict(row) for row in reversed(rows)]
        observed_gaps = []
        for previous, current in zip(records, records[1:]):
            delta = current["timestamp_ms"] - previous["timestamp_ms"]
            if delta > 0:
                observed_gaps.append({
                    "from_timestamp_ms": previous["timestamp_ms"],
                    "to_timestamp_ms": current["timestamp_ms"],
                    "observed_gap_ms": delta,
                })
        return {
            "status": "COMPLETED" if records else "NO_STORED_DATA",
            "market": market, "symbol": symbol, "period": period,
            "returned_count": len(records), "records": records,
            "coverage": {
                "first_timestamp_ms": records[0]["timestamp_ms"] if records else None,
                "last_timestamp_ms": records[-1]["timestamp_ms"] if records else None,
                "observed_gaps": observed_gaps,
                "expected_schedule_verified": False,
                "note": "Binance may omit periods with no trades; observed timestamp deltas are not classified as missing data.",
            },
            "source": "Local SQLite open-interest history; original source retained per record.",
        }
