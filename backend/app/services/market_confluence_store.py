from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from pathlib import Path
from typing import Any


class MarketConfluenceStore:
    """Persistent, idempotent storage for descriptive confluence snapshots."""

    def __init__(self, database_path: str) -> None:
        self.database_path = database_path
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(database_path) as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS market_confluence_snapshots (
                    snapshot_id TEXT PRIMARY KEY, market TEXT NOT NULL, symbol TEXT NOT NULL,
                    interval TEXT NOT NULL, analyzed_at_ms INTEGER NOT NULL, bias TEXT NOT NULL,
                    alignment TEXT NOT NULL, reference_price REAL, reference_close_time_ms INTEGER,
                    payload_json TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(market,symbol,interval,analyzed_at_ms))
            """)
            db.execute("""
                CREATE INDEX IF NOT EXISTS idx_confluence_history
                ON market_confluence_snapshots(market,symbol,interval,analyzed_at_ms DESC)
            """)

    @staticmethod
    def _integer(value: Any, field: str) -> int:
        if isinstance(value, bool):
            raise ValueError(f"{field} must be an integer timestamp")
        try:
            number = int(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"{field} must be an integer timestamp") from exc
        if isinstance(value, float) and not value.is_integer():
            raise ValueError(f"{field} must be an integer timestamp")
        return number

    def save(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("Snapshot payload must be an object")
        market = str(payload.get("market", "")).upper()
        symbol = str(payload.get("symbol", "")).strip().upper()
        interval = str(payload.get("interval", "")).strip()
        stamp = self._integer(payload.get("analyzed_at_ms"), "analyzed_at_ms")
        if market not in {"SPOT", "USD_M", "COIN_M"} or not symbol or not interval or stamp <= 0:
            raise ValueError("Snapshot requires valid market, symbol, interval and analyzed_at_ms")

        confluence = payload.get("confluence") or {}
        reference = payload.get("reference") or {}
        if not isinstance(confluence, dict) or not isinstance(reference, dict):
            raise ValueError("confluence and reference must be objects")
        bias = str(confluence.get("bias", "UNKNOWN")).upper()
        if bias not in {"BULLISH", "BEARISH", "MIXED", "UNKNOWN"}:
            raise ValueError("Unsupported confluence bias")
        alignment = str(confluence.get("alignment", "UNKNOWN"))

        raw_price = reference.get("price")
        if isinstance(raw_price, bool):
            raise ValueError("reference price must be finite and positive")
        try:
            price = float(raw_price) if raw_price is not None else None
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("reference price must be finite and positive") from exc
        if price is not None and (not math.isfinite(price) or price <= 0):
            raise ValueError("reference price must be finite and positive")

        raw_close = reference.get("close_time_ms")
        close = self._integer(raw_close, "reference close_time_ms") if raw_close is not None else None
        if price is not None and close is None:
            raise ValueError("reference close_time_ms is required with reference price")
        if close is not None and (close < 0 or close > stamp):
            raise ValueError("reference candle must be fully closed at or before analyzed_at_ms")

        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
        key = hashlib.sha256(f"{market}|{symbol}|{interval}|{stamp}".encode()).hexdigest()
        with sqlite3.connect(self.database_path) as db:
            db.execute("""
                INSERT OR IGNORE INTO market_confluence_snapshots
                (snapshot_id,market,symbol,interval,analyzed_at_ms,bias,alignment,
                 reference_price,reference_close_time_ms,payload_json)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (key, market, symbol, interval, stamp, bias, alignment, price, close, encoded))
            row = db.execute("""
                SELECT snapshot_id FROM market_confluence_snapshots
                WHERE market=? AND symbol=? AND interval=? AND analyzed_at_ms=?
            """, (market, symbol, interval, stamp)).fetchone()
        return {
            "status": "STORED", "snapshot_id": row[0], "market": market,
            "symbol": symbol, "interval": interval, "analyzed_at_ms": stamp, "bias": bias,
        }

    def history(
        self, market: str, symbol: str, interval: str = "1h", limit: int = 100
    ) -> dict[str, Any]:
        if market.upper() not in {"SPOT", "USD_M", "COIN_M"}:
            raise ValueError("Invalid market")
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        with sqlite3.connect(self.database_path) as db:
            db.row_factory = sqlite3.Row
            rows = db.execute("""
                SELECT * FROM market_confluence_snapshots
                WHERE market=? AND symbol=? AND interval=?
                ORDER BY analyzed_at_ms DESC LIMIT ?
            """, (market.upper(), symbol.upper(), interval, limit)).fetchall()
        snapshots = []
        for row in reversed(rows):
            item = dict(row)
            item["payload"] = json.loads(item.pop("payload_json"))
            snapshots.append(item)
        return {
            "status": "COMPLETED" if snapshots else "NO_STORED_SNAPSHOTS",
            "market": market.upper(), "symbol": symbol.upper(), "interval": interval,
            "returned_count": len(snapshots), "snapshots": snapshots,
            "source": "Local SQLite confluence snapshot store",
        }

    def get_snapshot(self, market: str, symbol: str, snapshot_id: str) -> dict[str, Any] | None:
        if market.upper() not in {"SPOT", "USD_M", "COIN_M"}:
            raise ValueError("Invalid market")
        with sqlite3.connect(self.database_path) as db:
            db.row_factory = sqlite3.Row
            row = db.execute("""
                SELECT * FROM market_confluence_snapshots
                WHERE snapshot_id=? AND market=? AND symbol=?
            """, (snapshot_id, market.upper(), symbol.upper())).fetchone()
        if row is None:
            return None
        item = dict(row)
        item["payload"] = json.loads(item.pop("payload_json"))
        return item
