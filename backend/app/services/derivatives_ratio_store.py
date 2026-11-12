from __future__ import annotations

import json
import math
import sqlite3
import psycopg
from psycopg.rows import dict_row
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.open_interest import OPEN_INTEREST_PERIODS


RATIO_TYPES = {"GLOBAL_LONG_SHORT", "TAKER_BUY_SELL"}


class DerivativesRatioStore:
    """Idempotent local storage for USD-M account and taker ratio observations."""

    def __init__(self, database_path: str, database_url: str = "") -> None:
        self.database_path = database_path
        self.database_url = database_url.strip()
        if self.database_url:
            return
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(database_path) as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS derivatives_ratio_history (
                    market TEXT NOT NULL,
                    ratio_type TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    period TEXT NOT NULL,
                    timestamp_ms INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    source TEXT NOT NULL,
                    collected_at TEXT NOT NULL,
                    PRIMARY KEY (market, ratio_type, symbol, period, timestamp_ms)
                )
            """)
            connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_derivatives_ratio_history
                ON derivatives_ratio_history(market, ratio_type, symbol, period, timestamp_ms)
            """)

    def _connect_postgres(self):
        return psycopg.connect(self.database_url, sslmode=("disable" if "sslmode=disable" in self.database_url else "require"), connect_timeout=15, row_factory=dict_row)

    @staticmethod
    def _number(row: dict[str, Any], key: str) -> float:
        try:
            value = row[key]
            if isinstance(value, bool):
                raise ValueError
            number = float(value)
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"Invalid ratio field: {key}") from exc
        if not math.isfinite(number) or number < 0:
            raise ValueError(f"Ratio field {key} must be finite and non-negative")
        return number

    @classmethod
    def _normalize(cls, ratio_type: str, row: Any) -> tuple[int, dict[str, Any]]:
        if not isinstance(row, dict):
            raise ValueError("Malformed Binance ratio record")
        try:
            timestamp = int(row["timestamp"])
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise ValueError("Invalid ratio timestamp") from exc
        if timestamp < 0:
            raise ValueError("Ratio timestamp must be non-negative")
        if ratio_type == "GLOBAL_LONG_SHORT":
            payload = {
                "long_short_ratio": cls._number(row, "longShortRatio"),
                "long_account": cls._number(row, "longAccount"),
                "short_account": cls._number(row, "shortAccount"),
            }
        elif ratio_type == "TAKER_BUY_SELL":
            payload = {
                "buy_sell_ratio": cls._number(row, "buySellRatio"),
                "buy_volume": cls._number(row, "buyVol"),
                "sell_volume": cls._number(row, "sellVol"),
            }
        else:
            raise ValueError("Unsupported ratio_type")
        return timestamp, payload

    def save(
        self, ratio_type: str, symbol: str, period: str, rows: list[Any],
        source: str = "Binance USD-M Futures public REST API",
    ) -> dict[str, Any]:
        ratio_type = ratio_type.upper()
        symbol = symbol.upper().strip()
        if ratio_type not in RATIO_TYPES:
            raise ValueError("Unsupported ratio_type")
        if not symbol or len(symbol) > 40:
            raise ValueError("Invalid symbol")
        if period not in OPEN_INTEREST_PERIODS:
            raise ValueError("Unsupported ratio period")
        if not isinstance(rows, list) or not 1 <= len(rows) <= 500:
            raise ValueError("rows must contain between 1 and 500 observations")
        normalized = []
        for row in rows:
            if not isinstance(row, dict) or str(row.get("symbol", "")).upper() != symbol:
                raise ValueError("Ratio record symbol does not match requested symbol")
            timestamp, payload = self._normalize(ratio_type, row)
            normalized.append((timestamp, payload))
        if len({item[0] for item in normalized}) != len(normalized):
            raise ValueError("Duplicate ratio timestamps in provider response")
        normalized.sort(key=lambda item: item[0])
        now = datetime.now(timezone.utc).isoformat()
        values = [
            ("USD_M", ratio_type, symbol, period, timestamp,
             json.dumps(payload, sort_keys=True, allow_nan=False), source, now)
            for timestamp, payload in normalized
        ]
        if self.database_url:
            with self._connect_postgres() as connection:
                connection.executemany("""
                    INSERT INTO public.derivatives_ratio_history (
                        market, ratio_type, symbol, period, timestamp_ms,
                        payload, source, collected_at
                    ) VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s)
                    ON CONFLICT(market, ratio_type, symbol, period, timestamp_ms)
                    DO UPDATE SET payload=excluded.payload, source=excluded.source,
                                  collected_at=excluded.collected_at
                """, [
                    (market, ratio_type, symbol, period, timestamp, payload, source, now)
                    for market, ratio_type, symbol, period, timestamp, payload, source, now in values
                ])
                total = connection.execute("""
                    SELECT COUNT(*) AS count FROM public.derivatives_ratio_history
                    WHERE market='USD_M' AND ratio_type=%s AND symbol=%s AND period=%s
                """, (ratio_type, symbol, period)).fetchone()["count"]
            storage = "POSTGRESQL"
        else:
            with sqlite3.connect(self.database_path) as connection:
                connection.executemany("""
                    INSERT INTO derivatives_ratio_history (
                        market, ratio_type, symbol, period, timestamp_ms,
                        payload_json, source, collected_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(market, ratio_type, symbol, period, timestamp_ms)
                    DO UPDATE SET payload_json=excluded.payload_json,
                                  source=excluded.source,
                                  collected_at=excluded.collected_at
                """, values)
                total = connection.execute("""
                    SELECT COUNT(*) FROM derivatives_ratio_history
                    WHERE market='USD_M' AND ratio_type=? AND symbol=? AND period=?
                """, (ratio_type, symbol, period)).fetchone()[0]
            storage = "SQLITE_IDEMPOTENT"
        return {
            "status": "COMPLETED", "market": "USD_M", "ratio_type": ratio_type,
            "symbol": symbol, "period": period, "received_count": len(rows),
            "stored_count": len(normalized), "total_stored_count": int(total),
            "first_timestamp_ms": normalized[0][0], "last_timestamp_ms": normalized[-1][0],
            "collected_at": now, "storage": storage, "source": source,
        }

    def history(
        self, ratio_type: str, symbol: str, period: str = "1h",
        start_time_ms: int | None = None, end_time_ms: int | None = None,
        limit: int = 500,
    ) -> dict[str, Any]:
        ratio_type = ratio_type.upper()
        symbol = symbol.upper().strip()
        if ratio_type not in RATIO_TYPES:
            raise ValueError("Unsupported ratio_type")
        if not symbol or len(symbol) > 40:
            raise ValueError("Invalid symbol")
        if period not in OPEN_INTEREST_PERIODS:
            raise ValueError("Unsupported ratio period")
        if not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500")
        if start_time_ms is not None and start_time_ms < 0:
            raise ValueError("start_time_ms must be non-negative")
        if end_time_ms is not None and end_time_ms < 0:
            raise ValueError("end_time_ms must be non-negative")
        if start_time_ms is not None and end_time_ms is not None and end_time_ms < start_time_ms:
            raise ValueError("end_time_ms must be >= start_time_ms")
        clauses = ["market='USD_M'", "ratio_type=?", "symbol=?", "period=?"]
        params: list[Any] = [ratio_type, symbol, period]
        if start_time_ms is not None:
            clauses.append("timestamp_ms>=?")
            params.append(start_time_ms)
        if end_time_ms is not None:
            clauses.append("timestamp_ms<=?")
            params.append(end_time_ms)
        params.append(limit)
        if self.database_url:
            pg_clauses = ["market='USD_M'", "ratio_type=%s", "symbol=%s", "period=%s"]
            pg_params: list[Any] = [ratio_type, symbol, period]
            if start_time_ms is not None:
                pg_clauses.append("timestamp_ms>=%s")
                pg_params.append(start_time_ms)
            if end_time_ms is not None:
                pg_clauses.append("timestamp_ms<=%s")
                pg_params.append(end_time_ms)
            pg_params.append(limit)
            with self._connect_postgres() as connection:
                rows = connection.execute(
                    f"SELECT timestamp_ms, payload, source, collected_at "
                    f"FROM public.derivatives_ratio_history WHERE {' AND '.join(pg_clauses)} "
                    "ORDER BY timestamp_ms DESC LIMIT %s", pg_params,
                ).fetchall()
            payload_key = "payload"
            source_label = "Neon PostgreSQL USD-M ratio history."
        else:
            with sqlite3.connect(self.database_path) as connection:
                connection.row_factory = sqlite3.Row
                rows = connection.execute(
                    f"SELECT timestamp_ms, payload_json, source, collected_at "
                    f"FROM derivatives_ratio_history WHERE {' AND '.join(clauses)} "
                    "ORDER BY timestamp_ms DESC LIMIT ?", params,
                ).fetchall()
            payload_key = "payload_json"
            source_label = "Locally stored Binance USD-M ratio observations."
        records = [{
            "timestamp_ms": row["timestamp_ms"],
            **(row[payload_key] if isinstance(row[payload_key], dict) else json.loads(row[payload_key])),
            "source": row["source"], "collected_at": row["collected_at"],
        } for row in reversed(rows)]
        return {
            "status": "COMPLETED" if records else "NO_STORED_DATA",
            "market": "USD_M", "ratio_type": ratio_type, "symbol": symbol,
            "period": period, "returned_count": len(records), "records": records,
            "source": source_label,
            "interpretation_warning": (
                "Account ratio counts accounts, not position size; taker ratio measures aggressive trade volume. "
                "Neither identifies all market participants or guarantees future price direction."
            ),
        }
