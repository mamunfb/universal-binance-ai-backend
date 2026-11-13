import asyncio
import json
import logging
import math
import sqlite3
import psycopg
from psycopg.rows import dict_row
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from websockets.asyncio.client import connect
from app.services.collector_leases import assert_collector_lease_owned

logger = logging.getLogger(__name__)
STREAM_URL = "wss://fstream.binance.com/market/ws/!forceOrder@arr"


def normalize_force_order(message: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(message, dict) or message.get("e") != "forceOrder" or not isinstance(message.get("o"), dict):
        return None
    order = message["o"]
    try:
        event_time_raw = message["E"]
        trade_time_raw = order.get("T") or event_time_raw
        if (isinstance(event_time_raw, bool) or isinstance(trade_time_raw, bool)):
            return None
        event_time = int(event_time_raw)
        trade_time = int(trade_time_raw)
        if event_time < 0 or trade_time < 0:
            return None

        def finite_nonnegative(value: Any, field: str) -> float:
            number = float(value or 0)
            if not math.isfinite(number) or number < 0:
                raise ValueError(f"Invalid liquidation {field}")
            return number

        avg_price = finite_nonnegative(order.get("ap"), "average price")
        original_qty = finite_nonnegative(order.get("q"), "original quantity")
        last_filled_qty = finite_nonnegative(order.get("l"), "last filled quantity")
        filled_qty = finite_nonnegative(order.get("z"), "cumulative filled quantity")
        notional = avg_price * filled_qty
        if not math.isfinite(notional):
            return None

        symbol = str(order.get("s", "")).strip().upper()
        if not symbol:
            return None
        side = str(order.get("S", "")).strip().upper()
        if side not in {"BUY", "SELL"}:
            return None
        raw_json = json.dumps(message, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError, KeyError, OverflowError):
        return None
    return {
        "event_time_ms": event_time,
        "trade_time_ms": trade_time,
        "symbol": symbol,
        "pair_symbol": str(order.get("ps", "")).strip().upper() or None,
        "market_type": message.get("st"),
        "side": side,
        "order_type": order.get("o"),
        "status": order.get("X"),
        "average_price": avg_price,
        "original_quantity": original_qty,
        "last_filled_quantity": last_filled_qty,
        "cumulative_filled_quantity": filled_qty,
        "approx_cumulative_notional": notional,
        "raw_json": raw_json,
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

    def insert(self, event: dict[str, Any], lease_owner_token: str | None = None) -> None:
        if self.database_url:
            with self._connect_postgres() as connection:
                if lease_owner_token is not None:
                    assert_collector_lease_owned(connection, "liquidation:all", lease_owner_token)
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
        if lease_owner_token is not None:
            raise RuntimeError("Distributed collector lease writes require PostgreSQL storage")
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

    def history(
        self, symbol: str | None = None, limit: int = 100,
        start_time_ms: int | None = None, end_time_ms: int | None = None,
    ) -> list[dict[str, Any]]:
        if not 1 <= limit <= 20000:
            raise ValueError("limit must be between 1 and 20000")
        if start_time_ms is not None and start_time_ms < 0:
            raise ValueError("start_time_ms must be non-negative")
        if end_time_ms is not None and end_time_ms < 0:
            raise ValueError("end_time_ms must be non-negative")
        if start_time_ms is not None and end_time_ms is not None and end_time_ms < start_time_ms:
            raise ValueError("end_time_ms must be >= start_time_ms")

        columns = (
            "event_time_ms, trade_time_ms, symbol, pair_symbol, market_type, side, "
            "status, average_price, cumulative_filled_quantity, approx_cumulative_notional"
        )
        if self.database_url:
            clauses: list[str] = []
            params: list[Any] = []
            if symbol:
                clauses.append("symbol=%s"); params.append(symbol.upper())
            if start_time_ms is not None:
                clauses.append("event_time_ms >= %s"); params.append(start_time_ms)
            if end_time_ms is not None:
                clauses.append("event_time_ms <= %s"); params.append(end_time_ms)
            query = "SELECT " + columns + " FROM public.liquidation_events"
            if clauses:
                query += " WHERE " + " AND ".join(clauses)
            query += " ORDER BY event_time_ms DESC, id DESC LIMIT %s"
            params.append(limit)
            with self._connect_postgres() as connection:
                return [dict(row) for row in connection.execute(query, params).fetchall()]

        clauses = []
        params_sql: list[Any] = []
        if symbol:
            clauses.append("symbol=?"); params_sql.append(symbol.upper())
        if start_time_ms is not None:
            clauses.append("event_time_ms>=?"); params_sql.append(start_time_ms)
        if end_time_ms is not None:
            clauses.append("event_time_ms<=?"); params_sql.append(end_time_ms)
        query = "SELECT " + columns + " FROM liquidation_events"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY event_time_ms DESC, id DESC LIMIT ?"
        params_sql.append(limit)
        with sqlite3.connect(self.database_path) as connection:
            connection.row_factory = sqlite3.Row
            return [dict(row) for row in connection.execute(query, params_sql)]

    def recent(self, symbol: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        return self.history(symbol=symbol, limit=limit)

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
        self._lease_owner_token: str | None = None

    def start(self, lease_owner_token: str | None = None) -> None:
        self._lease_owner_token = lease_owner_token
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
                            await asyncio.to_thread(self.store.insert, event, self._lease_owner_token)
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
            "coverage_warning": (
                "Binance publishes at most the latest force-order snapshot per symbol per 1000ms; "
                "this feed is not a complete liquidation tape or historical archive."
            ),
            "deduplication": (
                "Not applied: the documented public forceOrder payload has no stable event/order ID, "
                "so heuristic deduplication could discard distinct snapshots."
            ),
        }
