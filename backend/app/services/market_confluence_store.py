from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


class MarketConfluenceStore:
    """Persistent, idempotent storage for descriptive confluence snapshots.

    PostgreSQL is used when DATABASE_URL is configured. SQLite remains the
    local-development and test fallback.
    """

    def __init__(self, database_path: str, database_url: str = "") -> None:
        self.database_path = database_path
        self.database_url = database_url.strip()
        if self.database_url:
            # The production schema is managed by the checked-in DB migration.
            return
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(database_path) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS market_confluence_snapshots (
                snapshot_id TEXT PRIMARY KEY, market TEXT NOT NULL, symbol TEXT NOT NULL,
                interval TEXT NOT NULL, analyzed_at_ms INTEGER NOT NULL, bias TEXT NOT NULL,
                alignment TEXT NOT NULL, reference_price REAL, reference_close_time_ms INTEGER,
                payload_json TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(market,symbol,interval,analyzed_at_ms))""")
            db.execute("""CREATE INDEX IF NOT EXISTS idx_confluence_history
                ON market_confluence_snapshots(market,symbol,interval,analyzed_at_ms DESC)""")

    def _connect_postgres(self):
        return psycopg.connect(self.database_url, sslmode=("disable" if "sslmode=disable" in self.database_url else "require"), connect_timeout=15, row_factory=dict_row)

    @staticmethod
    def _validate(payload: dict[str, Any]) -> tuple[str, str, str, int, str, str, float | None, int | None, str, str]:
        market = str(payload.get("market", "")).upper()
        symbol = str(payload.get("symbol", "")).upper()
        interval = str(payload.get("interval", ""))
        stamp = int(payload.get("analyzed_at_ms") or 0)
        if market not in {"SPOT", "USD_M", "COIN_M"} or not symbol or not interval or stamp <= 0:
            raise ValueError("Snapshot requires valid market, symbol, interval and analyzed_at_ms")
        confluence = payload.get("confluence") or {}
        bias = str(confluence.get("bias", "UNKNOWN")).upper()
        if bias not in {"BULLISH", "BEARISH", "MIXED", "UNKNOWN"}:
            raise ValueError("Unsupported confluence bias")
        alignment = str(confluence.get("alignment", "UNKNOWN"))
        reference = payload.get("reference") or {}
        price = reference.get("price")
        price = float(price) if price is not None else None
        if price is not None and (not math.isfinite(price) or price <= 0):
            raise ValueError("reference price must be finite and positive")
        close = reference.get("close_time_ms")
        close = int(close) if close is not None and price is not None else None
        if price is not None and close is None:
            raise ValueError("reference close_time_ms is required with reference price")
        if close is not None and close > stamp:
            raise ValueError("reference candle must be fully closed at or before analyzed_at_ms")
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
        key = hashlib.sha256(f"{market}|{symbol}|{interval}|{stamp}".encode()).hexdigest()
        return market, symbol, interval, stamp, bias, alignment, price, close, encoded, key

    def save(self, payload: dict[str, Any]) -> dict[str, Any]:
        market, symbol, interval, stamp, bias, alignment, price, close, encoded, key = self._validate(payload)
        if self.database_url:
            with self._connect_postgres() as db:
                db.execute(
                    """INSERT INTO public.market_confluence_snapshots
                    (snapshot_id,market,symbol,interval,analyzed_at_ms,bias,alignment,
                     reference_price,reference_close_time_ms,payload)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (market,symbol,interval,analyzed_at_ms) DO NOTHING""",
                    (key, market, symbol, interval, stamp, bias, alignment, price, close, Jsonb(payload)),
                )
                row = db.execute(
                    """SELECT snapshot_id FROM public.market_confluence_snapshots
                    WHERE market=%s AND symbol=%s AND interval=%s AND analyzed_at_ms=%s""",
                    (market, symbol, interval, stamp),
                ).fetchone()
        else:
            with sqlite3.connect(self.database_path) as db:
                db.execute("""INSERT OR IGNORE INTO market_confluence_snapshots
                    (snapshot_id,market,symbol,interval,analyzed_at_ms,bias,alignment,reference_price,reference_close_time_ms,payload_json)
                    VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (key, market, symbol, interval, stamp, bias, alignment, price, close, encoded))
                row = db.execute("""SELECT snapshot_id FROM market_confluence_snapshots
                    WHERE market=? AND symbol=? AND interval=? AND analyzed_at_ms=?""",
                    (market, symbol, interval, stamp)).fetchone()
                row = {"snapshot_id": row[0]} if row else None
        if row is None:
            raise RuntimeError("Snapshot insert could not be confirmed")
        return {"status": "STORED", "snapshot_id": row["snapshot_id"], "market": market,
                "symbol": symbol, "interval": interval, "analyzed_at_ms": stamp, "bias": bias}

    @staticmethod
    def _decode_row(row: dict[str, Any]) -> dict[str, Any]:
        item = dict(row)
        payload = item.pop("payload", None)
        if payload is None:
            payload = json.loads(item.pop("payload_json"))
        item["payload"] = payload
        if hasattr(item.get("created_at"), "isoformat"):
            item["created_at"] = item["created_at"].isoformat()
        return item

    def history(self, market: str, symbol: str, interval: str = "1h", limit: int = 100) -> dict[str, Any]:
        normalized_market = market.upper()
        if normalized_market not in {"SPOT", "USD_M", "COIN_M"}:
            raise ValueError("Invalid market")
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        if self.database_url:
            with self._connect_postgres() as db:
                rows = db.execute("""SELECT * FROM public.market_confluence_snapshots
                    WHERE market=%s AND symbol=%s AND interval=%s
                    ORDER BY analyzed_at_ms DESC LIMIT %s""",
                    (normalized_market, symbol.upper(), interval, limit)).fetchall()
            snapshots = [self._decode_row(row) for row in reversed(rows)]
            source = "Neon PostgreSQL confluence snapshot store"
        else:
            with sqlite3.connect(self.database_path) as db:
                db.row_factory = sqlite3.Row
                rows = db.execute("""SELECT * FROM market_confluence_snapshots
                    WHERE market=? AND symbol=? AND interval=?
                    ORDER BY analyzed_at_ms DESC LIMIT ?""",
                    (normalized_market, symbol.upper(), interval, limit)).fetchall()
            snapshots = [self._decode_row(dict(row)) for row in reversed(rows)]
            source = "Local SQLite confluence snapshot store"
        return {"status": "COMPLETED" if snapshots else "NO_STORED_SNAPSHOTS",
                "market": normalized_market, "symbol": symbol.upper(), "interval": interval,
                "returned_count": len(snapshots), "snapshots": snapshots, "source": source}

    def get_snapshot(self, market: str, symbol: str, snapshot_id: str) -> dict[str, Any] | None:
        normalized_market = market.upper()
        if normalized_market not in {"SPOT", "USD_M", "COIN_M"}:
            raise ValueError("Invalid market")
        if self.database_url:
            with self._connect_postgres() as db:
                row = db.execute("""SELECT * FROM public.market_confluence_snapshots
                    WHERE snapshot_id=%s AND market=%s AND symbol=%s""",
                    (snapshot_id, normalized_market, symbol.upper())).fetchone()
        else:
            with sqlite3.connect(self.database_path) as db:
                db.row_factory = sqlite3.Row
                found = db.execute("""SELECT * FROM market_confluence_snapshots
                    WHERE snapshot_id=? AND market=? AND symbol=?""",
                    (snapshot_id, normalized_market, symbol.upper())).fetchone()
                row = dict(found) if found is not None else None
        return self._decode_row(row) if row is not None else None
