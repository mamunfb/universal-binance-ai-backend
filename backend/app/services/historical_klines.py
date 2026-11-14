from __future__ import annotations

import math
import sqlite3
import psycopg
from psycopg.rows import dict_row
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.collector_lease import (
    CollectorLease,
    CollectorLeaseLostError,
    PostgresCollectorLease,
)


class HistoricalKlineStore:
    """Idempotent local storage for validated Binance OHLCV candles."""

    def __init__(self, database_path: str, database_url: str = "") -> None:
        self.database_path = database_path
        self.database_url = database_url.strip()
        if self.database_url:
            return
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(database_path) as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS historical_klines (
                    market TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    interval TEXT NOT NULL,
                    open_time_ms INTEGER NOT NULL,
                    open REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    volume REAL NOT NULL,
                    close_time_ms INTEGER NOT NULL,
                    quote_volume REAL NOT NULL,
                    trade_count INTEGER NOT NULL,
                    taker_buy_base_volume REAL NOT NULL,
                    taker_buy_quote_volume REAL NOT NULL,
                    source TEXT NOT NULL,
                    collected_at TEXT NOT NULL,
                    PRIMARY KEY (market, symbol, interval, open_time_ms)
                )
            """)
            connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_historical_klines_lookup
                ON historical_klines(market, symbol, interval, open_time_ms)
            """)

    def _connect_postgres(self):
        return psycopg.connect(self.database_url, sslmode=("disable" if "sslmode=disable" in self.database_url else "require"), connect_timeout=15, row_factory=dict_row)

    @staticmethod
    def _finite(value: Any, field: str) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"Invalid candle {field}") from exc
        if not math.isfinite(number):
            raise ValueError(f"Invalid candle {field}")
        return number

    @classmethod
    def _normalize(cls, row: Any) -> tuple[Any, ...]:
        if not isinstance(row, (list, tuple)) or len(row) < 11:
            raise ValueError("Malformed Binance kline row; refusing to store partial history")
        try:
            if any(isinstance(row[index], bool) for index in (0, 6, 8)):
                raise ValueError
            open_time = int(row[0])
            close_time = int(row[6])
            trade_count = int(row[8])
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("Invalid candle timestamps or trade count") from exc
        open_price, high, low, close, volume, quote_volume, taker_base, taker_quote = (
            cls._finite(row[index], field)
            for index, field in (
                (1, "open"), (2, "high"), (3, "low"), (4, "close"),
                (5, "volume"), (7, "quote volume"),
                (9, "taker buy base volume"), (10, "taker buy quote volume"),
            )
        )
        if open_time < 0 or close_time < open_time or trade_count < 0:
            raise ValueError("Invalid candle timestamp range or trade count")
        if min(open_price, high, low, close) <= 0 or min(volume, quote_volume, taker_base, taker_quote) < 0:
            raise ValueError("Candle prices must be positive and volumes non-negative")
        if high < max(open_price, close, low) or low > min(open_price, close, high):
            raise ValueError("Inconsistent candle OHLC values")
        if taker_base > volume + max(1e-12, volume * 1e-9):
            raise ValueError("Taker-buy base volume exceeds total base volume")
        return (
            open_time, open_price, high, low, close, volume, close_time,
            quote_volume, trade_count, taker_base, taker_quote,
        )

    def save_klines(
        self, market: str, symbol: str, interval: str, rows: list[Any],
        source: str = "Binance public REST API",
        lease: CollectorLease | None = None,
    ) -> dict[str, Any]:
        market = market.upper()
        symbol = symbol.upper()
        if market not in {"SPOT", "USD_M", "COIN_M"}:
            raise ValueError("market must be SPOT, USD_M, or COIN_M")
        if not symbol.strip() or not interval.strip():
            raise ValueError("symbol and interval must not be empty")
        if not isinstance(rows, list) or not 1 <= len(rows) <= 1500:
            raise ValueError("rows must contain between 1 and 1500 candles")
        normalized = [self._normalize(row) for row in rows]
        if len({row[0] for row in normalized}) != len(normalized):
            raise ValueError("Duplicate candle open times in provider response")
        normalized.sort(key=lambda row: row[0])
        now = datetime.now(timezone.utc).isoformat()
        values = [
            (market, symbol, interval, *row, source, now)
            for row in normalized
        ]
        if lease is not None and not self.database_url:
            raise ValueError("Collector leases require PostgreSQL-backed historical storage")
        if self.database_url:
            with self._connect_postgres() as connection:
                if lease is not None and not PostgresCollectorLease.lock_if_owned(connection, lease):
                    raise CollectorLeaseLostError(
                        "Historical kline write rejected because the collector lease is no longer owned"
                    )
                connection.cursor().executemany("""
                    INSERT INTO public.historical_klines (
                        market, symbol, interval, open_time_ms, open, high, low, close,
                        volume, close_time_ms, quote_volume, trade_count,
                        taker_buy_base_volume, taker_buy_quote_volume, source, collected_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT(market, symbol, interval, open_time_ms) DO UPDATE SET
                        open=excluded.open, high=excluded.high, low=excluded.low,
                        close=excluded.close, volume=excluded.volume,
                        close_time_ms=excluded.close_time_ms,
                        quote_volume=excluded.quote_volume, trade_count=excluded.trade_count,
                        taker_buy_base_volume=excluded.taker_buy_base_volume,
                        taker_buy_quote_volume=excluded.taker_buy_quote_volume,
                        source=excluded.source, collected_at=excluded.collected_at
                """, values)
                total = connection.execute("""
                    SELECT COUNT(*) AS count FROM public.historical_klines
                    WHERE market=%s AND symbol=%s AND interval=%s
                """, (market, symbol, interval)).fetchone()["count"]
            storage = "POSTGRESQL"
        else:
            with sqlite3.connect(self.database_path) as connection:
                connection.executemany("""
                    INSERT INTO historical_klines (
                        market, symbol, interval, open_time_ms, open, high, low, close,
                        volume, close_time_ms, quote_volume, trade_count,
                        taker_buy_base_volume, taker_buy_quote_volume, source, collected_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(market, symbol, interval, open_time_ms) DO UPDATE SET
                        open=excluded.open, high=excluded.high, low=excluded.low,
                        close=excluded.close, volume=excluded.volume,
                        close_time_ms=excluded.close_time_ms,
                        quote_volume=excluded.quote_volume, trade_count=excluded.trade_count,
                        taker_buy_base_volume=excluded.taker_buy_base_volume,
                        taker_buy_quote_volume=excluded.taker_buy_quote_volume,
                        source=excluded.source, collected_at=excluded.collected_at
                """, values)
                total = connection.execute("""
                    SELECT COUNT(*) FROM historical_klines
                    WHERE market=? AND symbol=? AND interval=?
                """, (market, symbol, interval)).fetchone()[0]
            storage = "SQLITE_IDEMPOTENT"
        return {
            "status": "COMPLETED",
            "market": market,
            "symbol": symbol,
            "interval": interval,
            "received_count": len(rows),
            "stored_count": len(normalized),
            "total_stored_count": int(total),
            "first_open_time_ms": normalized[0][0],
            "last_open_time_ms": normalized[-1][0],
            "collected_at": now,
            "source": source,
            "storage": storage,
        }

    def latest_open_time(self, market: str, symbol: str, interval: str) -> int | None:
        """Return the newest locally stored candle open time for one series."""
        if market.upper() not in {"SPOT", "USD_M", "COIN_M"}:
            raise ValueError("market must be SPOT, USD_M, or COIN_M")
        if not symbol.strip() or not interval.strip():
            raise ValueError("symbol and interval must not be empty")
        if self.database_url:
            with self._connect_postgres() as connection:
                row = connection.execute(
                    """SELECT MAX(open_time_ms) AS latest FROM public.historical_klines
                       WHERE market=%s AND symbol=%s AND interval=%s""",
                    (market.upper(), symbol.upper(), interval),
                ).fetchone()
            value = row["latest"] if row else None
        else:
            with sqlite3.connect(self.database_path) as connection:
                row = connection.execute(
                    """SELECT MAX(open_time_ms) FROM historical_klines
                       WHERE market=? AND symbol=? AND interval=?""",
                    (market.upper(), symbol.upper(), interval),
                ).fetchone()
            value = row[0] if row else None
        return int(value) if value is not None else None

    def history(
        self, market: str, symbol: str, interval: str,
        start_time_ms: int | None = None, end_time_ms: int | None = None,
        limit: int = 1000,
    ) -> dict[str, Any]:
        if market.upper() not in {"SPOT", "USD_M", "COIN_M"}:
            raise ValueError("market must be SPOT, USD_M, or COIN_M")
        if not symbol.strip() or not interval.strip():
            raise ValueError("symbol and interval must not be empty")
        if not 1 <= limit <= 5000:
            raise ValueError("limit must be between 1 and 5000")
        if start_time_ms is not None and start_time_ms < 0:
            raise ValueError("start_time_ms must be non-negative")
        if end_time_ms is not None and end_time_ms < 0:
            raise ValueError("end_time_ms must be non-negative")
        if start_time_ms is not None and end_time_ms is not None and end_time_ms < start_time_ms:
            raise ValueError("end_time_ms must be >= start_time_ms")
        clauses = ["market=?", "symbol=?", "interval=?"]
        params: list[Any] = [market.upper(), symbol.upper(), interval]
        if start_time_ms is not None:
            clauses.append("open_time_ms>=?")
            params.append(start_time_ms)
        if end_time_ms is not None:
            clauses.append("open_time_ms<=?")
            params.append(end_time_ms)
        params.append(limit)
        if self.database_url:
            pg_clauses = ["market=%s", "symbol=%s", "interval=%s"]
            pg_params: list[Any] = [market.upper(), symbol.upper(), interval]
            if start_time_ms is not None:
                pg_clauses.append("open_time_ms>=%s")
                pg_params.append(start_time_ms)
            if end_time_ms is not None:
                pg_clauses.append("open_time_ms<=%s")
                pg_params.append(end_time_ms)
            pg_params.append(limit)
            with self._connect_postgres() as connection:
                rows = connection.execute(f"""
                    SELECT open_time_ms, open, high, low, close, volume, close_time_ms,
                           quote_volume, trade_count, taker_buy_base_volume,
                           taker_buy_quote_volume, source, collected_at
                    FROM public.historical_klines WHERE {' AND '.join(pg_clauses)}
                    ORDER BY open_time_ms DESC LIMIT %s
                """, pg_params).fetchall()
            candles = [dict(row) for row in reversed(rows)]
            storage_source = "Neon PostgreSQL historical store"
        else:
            with sqlite3.connect(self.database_path) as connection:
                connection.row_factory = sqlite3.Row
                rows = connection.execute(f"""
                    SELECT open_time_ms, open, high, low, close, volume, close_time_ms,
                           quote_volume, trade_count, taker_buy_base_volume,
                           taker_buy_quote_volume, source, collected_at
                    FROM historical_klines WHERE {' AND '.join(clauses)}
                    ORDER BY open_time_ms DESC LIMIT ?
                """, params).fetchall()
            candles = [dict(row) for row in reversed(rows)]
            storage_source = "Local SQLite historical store"
        return {
            "status": "COMPLETED" if candles else "NO_STORED_DATA",
            "market": market.upper(),
            "symbol": symbol.upper(),
            "interval": interval,
            "returned_count": len(candles),
            "candles": candles,
            "coverage": {
                "first_open_time_ms": candles[0]["open_time_ms"] if candles else None,
                "last_open_time_ms": candles[-1]["open_time_ms"] if candles else None,
                "contiguous": None,
                "note": "Contiguous interval coverage is not yet verified; returned rows may contain gaps.",
            },
            "source": f"{storage_source}; original candle source retained per row.",
        }
