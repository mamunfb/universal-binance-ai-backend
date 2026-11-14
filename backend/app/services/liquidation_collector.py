import asyncio
import hashlib
import json
import logging
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

from websockets.asyncio.client import connect

logger = logging.getLogger(__name__)


async def _wait_for_worker_task(task: asyncio.Task) -> tuple[Any, BaseException | None]:
    """Drain a blocking worker even if its owning task is cancelled repeatedly."""
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            continue
        except BaseException:
            break
    try:
        return task.result(), None
    except BaseException as exc:
        return None, exc


STREAM_URL = "wss://fstream.binance.com/market/ws/!forceOrder@arr"


def _event_fingerprint(event: dict[str, Any]) -> str:
    raw_payload = json.loads(event["raw_json"])
    event_fields = {
        key: event.get(key)
        for key in (
            "event_time_ms", "trade_time_ms", "symbol", "pair_symbol", "market_type",
            "side", "order_type", "status", "average_price", "original_quantity",
            "last_filled_quantity", "cumulative_filled_quantity",
            "approx_cumulative_notional",
        )
    }
    canonical = json.dumps(
        {"raw_payload": raw_payload, "event_fields": event_fields},
        sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


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
    event = {
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
    event["event_fingerprint"] = _event_fingerprint(event)
    return event


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
                    raw_json TEXT NOT NULL,
                    event_fingerprint TEXT
                )
            """)
            columns = {row[1] for row in connection.execute("PRAGMA table_info(liquidation_events)")}
            if "event_fingerprint" not in columns:
                connection.execute("ALTER TABLE liquidation_events ADD COLUMN event_fingerprint TEXT")
            connection.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_liquidation_event_fingerprint "
                "ON liquidation_events(event_fingerprint)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_liquidation_symbol_time "
                "ON liquidation_events(symbol, event_time_ms)"
            )

    def _connect_postgres(self):
        return psycopg.connect(self.database_url, sslmode=("disable" if "sslmode=disable" in self.database_url else "require"), connect_timeout=15, row_factory=dict_row)

    def insert(self, event: dict[str, Any], lease: CollectorLease | None = None) -> None:
        event_fingerprint = _event_fingerprint(event)
        if lease is not None and not self.database_url:
            raise ValueError("Collector leases require PostgreSQL-backed liquidation storage")
        if self.database_url:
            with self._connect_postgres() as connection:
                if lease is not None and not PostgresCollectorLease.lock_if_owned(connection, lease):
                    raise CollectorLeaseLostError(
                        "Liquidation write rejected because the collector lease is no longer owned"
                    )
                connection.execute("""
                    INSERT INTO public.liquidation_events (
                        event_time_ms, trade_time_ms, symbol, pair_symbol, market_type, side,
                        order_type, status, average_price, original_quantity, last_filled_quantity,
                        cumulative_filled_quantity, approx_cumulative_notional, raw_payload, event_fingerprint
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s)
                    ON CONFLICT (event_fingerprint) DO NOTHING
                """, (
                    event["event_time_ms"], event["trade_time_ms"], event["symbol"],
                    event.get("pair_symbol"), event.get("market_type"), event.get("side"),
                    event.get("order_type"), event.get("status"), event.get("average_price"),
                    event.get("original_quantity"), event.get("last_filled_quantity"),
                    event.get("cumulative_filled_quantity"), event.get("approx_cumulative_notional"),
                    event["raw_json"], event_fingerprint,
                ))
            return
        columns = (
            "event_time_ms, trade_time_ms, symbol, pair_symbol, market_type, side, "
            "order_type, status, average_price, original_quantity, last_filled_quantity, "
            "cumulative_filled_quantity, approx_cumulative_notional, raw_json, event_fingerprint"
        )
        values = tuple(event[key] for key in columns.split(", ") if key != "event_fingerprint") + (event_fingerprint,)
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                f"INSERT INTO liquidation_events ({columns}) VALUES ({','.join(['?'] * len(values))}) "
                "ON CONFLICT(event_fingerprint) DO NOTHING",
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
    def __init__(
        self, store: LiquidationStore, lease_database_url: str = "",
        lease_name: str = "liquidation-stream-collector",
        lease_ttl_seconds: int = 30,
    ) -> None:
        self.store = store
        self._lease_coordinator = (
            PostgresCollectorLease(
                lease_database_url, lease_name, ttl_seconds=lease_ttl_seconds
            ) if lease_database_url.strip() else None
        )
        self._lease: CollectorLease | None = None
        self._lease_lost = asyncio.Event()
        self._lease_state = "NOT_REQUIRED" if self._lease_coordinator is None else "WAITING"
        self.task: asyncio.Task | None = None
        self.connected = False
        self.last_message_at: str | None = None
        self.last_error: str | None = None
        self.storage_error: str | None = None
        self.storage_retry_count = 0
        self.reconnect_count = 0
        self.received_count = 0

    def start(self) -> None:
        if self.task is None or self.task.done():
            self._lease_lost.clear()
            self.task = asyncio.create_task(self.run())

    async def stop(self) -> None:
        task = self.task
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self.connected = False
        if self._lease is not None and self._lease_coordinator is not None:
            lease = self._lease
            self._lease = None
            if not self._lease_lost.is_set():
                release_worker = asyncio.create_task(
                    asyncio.to_thread(self._lease_coordinator.release, lease)
                )
                released, release_error = await _wait_for_worker_task(release_worker)
                if release_error is not None:
                    self._lease_state = "RELEASE_FAILED"
                    self.last_error = type(release_error).__name__
                else:
                    self._lease_state = "RELEASED" if released else "RELEASE_FAILED"
        if self._lease_state not in {"LOST", "RELEASE_FAILED", "ACQUIRE_FAILED"}:
            self._lease_state = "STOPPED" if self._lease_coordinator else "NOT_REQUIRED"

    async def _run_stream(self) -> None:
        delay = 1
        while not self._lease_lost.is_set():
            try:
                async with connect(STREAM_URL, ping_interval=20, ping_timeout=20, close_timeout=10) as socket:
                    self.connected = True
                    self.last_error = None
                    delay = 1
                    async for raw in socket:
                        if self._lease_lost.is_set():
                            return
                        payload = json.loads(raw)
                        messages = payload if isinstance(payload, list) else [payload]
                        for message in messages:
                            event = normalize_force_order(message)
                            if event is None:
                                continue
                            await self._persist_event(event)
                            self.received_count += 1
                            self.last_message_at = datetime.now(timezone.utc).isoformat()
            except asyncio.CancelledError:
                raise
            except CollectorLeaseLostError:
                self._lease_state = "LOST"
                self._lease_lost.set()
                raise
            except Exception as exc:
                if self._lease_lost.is_set():
                    return
                self.connected = False
                error_type = type(exc).__name__
                self.last_error = error_type
                self.reconnect_count += 1
                logger.warning(
                    "Liquidation stream disconnected (%s); retrying in %s seconds",
                    error_type, delay,
                )
                await asyncio.sleep(delay)
                delay = min(delay * 2, 60)
            finally:
                self.connected = False

    async def _renew_lease_loop(self) -> None:
        assert self._lease_coordinator is not None
        interval = max(1.0, self._lease_coordinator.ttl_seconds / 3)
        while not self._lease_lost.is_set():
            await asyncio.sleep(interval)
            lease = self._lease
            if lease is None:
                self._lease_state = "LOST"
                self._lease_lost.set()
                return
            renew_worker = asyncio.create_task(
                asyncio.to_thread(self._lease_coordinator.renew, lease)
            )
            try:
                renewed = await asyncio.shield(renew_worker)
            except asyncio.CancelledError:
                renewed_during_shutdown, renew_error = await _wait_for_worker_task(renew_worker)
                if renew_error is not None:
                    self.last_error = type(renew_error).__name__
                elif renewed_during_shutdown is not None:
                    self._lease = renewed_during_shutdown
                else:
                    self._lease_state = "LOST"
                    self._lease_lost.set()
                raise
            except Exception as exc:
                self.last_error = type(exc).__name__
                renewed = None
            if renewed is None:
                self._lease_state = "LOST"
                self._lease_lost.set()
                return
            self._lease = renewed

    async def run(self) -> None:
        if self._lease_coordinator is None:
            await self._run_stream()
            return
        while not self._lease_lost.is_set():
            acquire_task = asyncio.create_task(
                asyncio.to_thread(self._lease_coordinator.acquire)
            )
            try:
                lease = await asyncio.shield(acquire_task)
            except asyncio.CancelledError:
                # Drain acquisition, then release any lease obtained during shutdown.
                acquired_during_shutdown, acquire_error = await _wait_for_worker_task(acquire_task)
                if acquire_error is not None:
                    self.last_error = type(acquire_error).__name__
                    self._lease_state = "ACQUIRE_FAILED"
                elif acquired_during_shutdown is not None:
                    release_worker = asyncio.create_task(
                        asyncio.to_thread(
                            self._lease_coordinator.release, acquired_during_shutdown
                        )
                    )
                    released, release_error = await _wait_for_worker_task(release_worker)
                    if release_error is not None:
                        self.last_error = type(release_error).__name__
                        self._lease_state = "RELEASE_FAILED"
                    else:
                        self._lease_state = "RELEASED" if released else "RELEASE_FAILED"
                else:
                    self._lease_state = "STOPPED"
                raise
            except Exception as exc:
                self._lease_state = "ACQUIRE_FAILED"
                self.last_error = type(exc).__name__
                await asyncio.sleep(10)
                continue
            if lease is None:
                self._lease_state = "HELD_BY_OTHER"
                await asyncio.sleep(10)
                continue
            self._lease = lease
            self._lease_state = "OWNED"
            stream_task = asyncio.create_task(self._run_stream())
            renew_task = asyncio.create_task(self._renew_lease_loop())
            try:
                done, pending = await asyncio.wait(
                    {stream_task, renew_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for task in pending:
                    task.cancel()
                await asyncio.gather(*pending, return_exceptions=True)
                for task in done:
                    exception = task.exception()
                    if exception is not None:
                        raise exception
            except asyncio.CancelledError:
                stream_task.cancel()
                renew_task.cancel()
                await _wait_for_worker_task(stream_task)
                await _wait_for_worker_task(renew_task)
                raise
            except CollectorLeaseLostError:
                self._lease_state = "LOST"
                self._lease_lost.set()
            finally:
                for task in (stream_task, renew_task):
                    if not task.done():
                        task.cancel()
                await _wait_for_worker_task(stream_task)
                await _wait_for_worker_task(renew_task)
            if self._lease_lost.is_set():
                self._lease_state = "LOST"
                break
            # A stream task should only finish on cancellation or lease loss.
            break

    async def _persist_event(self, event: dict[str, Any]) -> None:
        """Persist with bounded retries; lease loss is terminal, not retryable."""
        delay = 1
        while True:
            try:
                insert_worker = asyncio.create_task(
                    asyncio.to_thread(
                        self.store.insert, event, **({} if self._lease is None else {"lease": self._lease})
                    )
                )
                try:
                    await asyncio.shield(insert_worker)
                except asyncio.CancelledError:
                    _, insert_error = await _wait_for_worker_task(insert_worker)
                    if isinstance(insert_error, CollectorLeaseLostError):
                        self._lease_state = "LOST"
                        self._lease_lost.set()
                    raise
            except asyncio.CancelledError:
                raise
            except CollectorLeaseLostError:
                self._lease_state = "LOST"
                self._lease_lost.set()
                raise
            except Exception as exc:
                error_type = type(exc).__name__
                self.storage_error = error_type
                self.storage_retry_count += 1
                logger.warning(
                    "Liquidation storage write failed (%s); retrying in %s seconds",
                    error_type, delay,
                )
                await asyncio.sleep(delay)
                delay = min(delay * 2, 60)
            else:
                self.storage_error = None
                return

    def status(self) -> dict[str, Any]:
        storage_status = "DEGRADED" if self.storage_error else "AVAILABLE"
        storage_error = self.storage_error
        try:
            stored_event_count = self.store.count()
        except Exception as exc:
            stored_event_count = None
            storage_status = "UNAVAILABLE"
            storage_error = type(exc).__name__
        return {
            "collector_enabled": True,
            "connected": self.connected,
            "stream": STREAM_URL,
            "received_since_process_start": self.received_count,
            "stored_event_count": stored_event_count,
            "storage_status": storage_status,
            "storage_error": storage_error,
            "storage_retry_count": self.storage_retry_count,
            "reconnect_count": self.reconnect_count,
            "last_message_at": self.last_message_at,
            "last_error": self.last_error,
            "lease_state": self._lease_state,
            "lease_name": (
                self._lease_coordinator.lease_name
                if self._lease_coordinator is not None else None
            ),
            "lease_fencing_token": (
                self._lease.fencing_token if self._lease is not None else None
            ),
            "warning": (
                "PostgreSQL lease fencing coordinates the scheduled liquidation stream only; "
                "manual collection paths and other collector families are not coordinated."
                if self._lease_coordinator is not None else
                "SQLite-backed liquidation collection remains single-process-only."
            ),
            "status": "CONNECTED" if self.connected else "DISCONNECTED_OR_STARTING",
        }
