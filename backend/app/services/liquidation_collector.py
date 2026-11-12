import asyncio
import json
import logging
import sqlite3
import psycopg
from psycopg.rows import dict_row
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from websockets.asyncio.client import connect

logger = logging.getLogger(__name__)
STREAM_URL = "wss://fstream.binance.com/market/ws/!forceOrder@arr"


def normalize_force_order(message: dict[str, Any]) -> dict[str, Any] | None:
    if message.get("e") != "forceOrder" or not isinstance(message.get("o"), dict):
        return None
    order = message["o"]
    try:
        avg_price = float(order.get("ap") or 0)
        filled_qty = float(order.get("z") or 0)
        event_time = int(message["E"])
        trade_time = int(order.get("T") or event_time)
        if avg_price < 0 or filled_qty < 0:
            return None
    except (TypeError, ValueError, KeyError):
        return None
    return {
        "event_time_ms": event_time,
        "trade_time_ms": trade_time,
        "symbol": str(order.get("s", "")).upper(),
        "pair_symbol": str(order.get("ps", "")).upper() or None,
        "market_type": message.get("st"),
        "side": str(order.get("S", "")).upper(),
        "order_type": order.get("o"),
        "status": order.get("X"),
        "average_price": avg_price,
        "original_quantity": float(order.get("q") or 0),
        "last_filled_quantity": float(order.get("l") or 0),
        "cumulative_filled_quantity": filled_qty,
        "approx_cumulative_notional": avg_price * filled_qty,
        "raw_json": json.dumps(message, separators=(",", ":"), ensure_ascii=False),
    }


class LiquidationStore:
    def __init__(self, database_path: str, database_url: str = "") -> None:
        self.database_path = database_path
        self.database_url = database_url.strip()
        if self.database_url:
            return
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(database_path) as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS liquidation_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_time_ms INTEGER NOT NULL,
                    trade_time_ms INTEGER NOT NULL,
                    symbol TEXT NOT NULL,
                    pair_symbol TEXT,
                    market_type INTEGER,
                    side TEXT,
                    order_type TEXT,
                    status TEXT,
                    average_price REAL,
                    original_quantity REAL,
                    last_filled_quantity REAL,
                    cumulative_filled_quantity REAL,
                    approx_cumulative_notional REAL,
                    raw_json TEXT NOT NULL
                )
            """)
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_liquidation_symbol_time "
                "ON liquidation_events(symbol, event_time_ms)"
            )

    def _connect_postgres(self):
        return psycopg.connect(self.database_url, sslmode=("disable" if "sslmode=disable" in self.database_url else "require"), connect_timeout=15, row_factory=dict_row)

    def insert(self, event: dict[str, Any]) -> None:
        if self.database_url:
            with self._connect_postgres() as connection:
                connection.execute("""
                    INSERT INTO public.liquidation_events (
                        event_time_ms, trade_time_ms, symbol, pair_symbol, market_type, side,
                        order_type, status, average_price, original_quantity, last_filled_quantity,
                        cumulative_filled_quantity, approx_cumulative_notional, raw_payload
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
                """, (
                    event["event_time_ms"], event["trade_time_ms"], event["symbol"],
                    event.get("pair_symbol"), event.get("market_type"), event.get("side"),
                    event.get("order_type"), event.get("status"), event.get("average_price"),
                    event.get("original_quantity"), event.get("last_filled_quantity"),
                    event.get("cumulative_filled_quantity"), event.get("approx_cumulative_notional"),
                    event["raw_json"],
                ))
            return
        columns = (
            "event_time_ms, trade_time_ms, symbol, pair_symbol, market_type, side, "
            "order_type, status, average_price, original_quantity, last_filled_quantity, "
            "cumulative_filled_quantity, approx_cumulative_notional, raw_json"
        )
        values = tuple(event[key] for key in columns.split(", "))
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                f"INSERT INTO liquidation_events ({columns}) VALUES ({','.join(['?'] * len(values))})",
                values,
            )

    def recent(self, symbol: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        if self.database_url:
            query = "SELECT event_time_ms, trade_time_ms, symbol, pair_symbol, market_type, side, status, average_price, cumulative_filled_quantity, approx_cumulative_notional FROM public.liquidation_events"
            params: list[Any] = []
            if symbol:
                query += " WHERE symbol=%s"; params.append(symbol.upper())
            query += " ORDER BY event_time_ms DESC, id DESC LIMIT %s"; params.append(limit)
            with self._connect_postgres() as connection:
                return [dict(row) for row in connection.execute(query, params).fetchall()]
        query = "SELECT event_time_ms, trade_time_ms, symbol, pair_symbol, market_type, side, status, average_price, cumulative_filled_quantity, approx_cumulative_notional FROM liquidation_events"
        params: tuple[Any, ...] = ()
        if symbol:
            query += " WHERE symbol = ?"
            params = (symbol.upper(),)
        query += " ORDER BY event_time_ms DESC LIMIT ?"
        params = (*params, limit)
        with sqlite3.connect(self.database_path) as connection:
            connection.row_factory = sqlite3.Row
            return [dict(row) for row in connection.execute(query, params).fetchall()]

    def count(self) -> int:
        if self.database_url:
            with self._connect_postgres() as connection:
                return int(connection.execute("SELECT COUNT(*) AS count FROM public.liquidation_events").fetchone()["count"])
        with sqlite3.connect(self.database_path) as connection:
            return int(connection.execute("SELECT COUNT(*) FROM liquidation_events").fetchone()[0])


class LiquidationCollector:
    def __init__(self, store: LiquidationStore) -> None:
        self.store = store
        self.task: asyncio.Task | None = None
        self.connected = False
        self.last_message_at: str | None = None
        self.last_error: str | None = None
        self.reconnect_count = 0
        self.received_count = 0

    def start(self) -> None:
        if self.task is None or self.task.done():
            self.task = asyncio.create_task(self.run())

    async def stop(self) -> None:
        if self.task and not self.task.done():
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        self.connected = False

    async def run(self) -> None:
        delay = 1
        while True:
            try:
                async with connect(STREAM_URL, ping_interval=20, ping_timeout=20, close_timeout=10) as socket:
                    self.connected = True
                    self.last_error = None
                    delay = 1
                    async for raw in socket:
                        payload = json.loads(raw)
                        messages = payload if isinstance(payload, list) else [payload]
                        for message in messages:
                            event = normalize_force_order(message)
                            if event is None:
                                continue
                            await asyncio.to_thread(self.store.insert, event)
                            self.received_count += 1
                            self.last_message_at = datetime.now(timezone.utc).isoformat()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.connected = False
                self.last_error = str(exc)
                self.reconnect_count += 1
                logger.exception("Liquidation stream disconnected; retrying in %s seconds", delay)
                await asyncio.sleep(delay)
                delay = min(delay * 2, 60)
            finally:
                self.connected = False

    def status(self) -> dict[str, Any]:
        return {
            "collector_enabled": True,
            "connected": self.connected,
            "stream": STREAM_URL,
            "received_since_process_start": self.received_count,
            "stored_event_count": self.store.count(),
            "reconnect_count": self.reconnect_count,
            "last_message_at": self.last_message_at,
            "last_error": self.last_error,
            "status": "CONNECTED" if self.connected else "DISCONNECTED_OR_STARTING",
        }
