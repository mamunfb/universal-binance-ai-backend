from __future__ import annotations

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

from app.services.collector_lease import (
    CollectorLease,
    CollectorLeaseLostError,
    PostgresCollectorLease,
)
from urllib.parse import quote

from websockets.asyncio.client import connect

logger = logging.getLogger(__name__)


def aggregate_trade_stream_url(market: str, symbol: str) -> str:
    market = market.upper()
    stream = f"{quote(symbol.lower(), safe='')}@aggTrade"
    if market == "SPOT":
        return f"wss://stream.binance.com:9443/ws/{stream}"
    if market == "USD_M":
        return f"wss://fstream.binance.com/market/ws/{stream}"
    if market == "COIN_M":
        return f"wss://dstream.binance.com/ws/{stream}"
    raise ValueError("market must be SPOT, USD_M or COIN_M")


def normalize_aggregate_trade(payload: dict[str, Any], market: str) -> dict[str, Any] | None:
    if not isinstance(payload, dict) or payload.get("e") != "aggTrade":
        return None
    try:
        normalized_market = market.upper()
        if normalized_market not in {"SPOT", "USD_M", "COIN_M"}:
            return None
        raw_symbol = payload["s"]
        if not isinstance(raw_symbol, str):
            return None
        symbol = raw_symbol.strip().upper()
        if not symbol or len(symbol) > 40:
            return None
        raw_trade_id = payload["a"]
        raw_event_time = payload["E"]
        raw_trade_time = payload["T"]
        if any(isinstance(value, bool) for value in (raw_trade_id, raw_event_time, raw_trade_time)):
            return None
        if any(
            isinstance(value, float) and not value.is_integer()
            for value in (raw_trade_id, raw_event_time, raw_trade_time)
        ):
            return None
        trade_id = int(raw_trade_id)
        event_time_ms = int(raw_event_time)
        trade_time_ms = int(raw_trade_time)
        price = float(payload["p"])
        quantity = float(payload["q"])
        buyer_is_maker = payload["m"]
        notional = price * quantity
        if (
            trade_id < 0 or event_time_ms < 0 or trade_time_ms < 0
            or not math.isfinite(price) or not math.isfinite(quantity)
            or price <= 0 or quantity <= 0
            or not math.isfinite(notional) or notional <= 0
        ):
            return None
        if not isinstance(buyer_is_maker, bool):
            return None
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError):
        return None
    return {
        "market": normalized_market, "symbol": symbol, "trade_id": trade_id,
        "event_time_ms": event_time_ms, "trade_time_ms": trade_time_ms,
        "price": price, "quantity": quantity, "notional": notional,
        "buyer_is_maker": buyer_is_maker,
        "aggressor_side": "SELL" if buyer_is_maker else "BUY",
        "raw_json": json.dumps(payload, separators=(",", ":")),
    }


class AggregateTradeStore:
    def __init__(self, database_path: str, database_url: str = "") -> None:
        self.database_path = database_path
        self.database_url = database_url.strip()
        if self.database_url:
            return
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(database_path) as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS aggregate_trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    market TEXT NOT NULL, symbol TEXT NOT NULL, trade_id INTEGER NOT NULL,
                    event_time_ms INTEGER NOT NULL, trade_time_ms INTEGER NOT NULL,
                    price REAL NOT NULL, quantity REAL NOT NULL, notional REAL NOT NULL,
                    buyer_is_maker INTEGER NOT NULL, aggressor_side TEXT NOT NULL,
                    raw_json TEXT NOT NULL,
                    UNIQUE(market, symbol, trade_id)
                )
            """)
            db.execute("""
                CREATE INDEX IF NOT EXISTS idx_aggregate_trades_market_symbol_time
                ON aggregate_trades(market, symbol, trade_time_ms)
            """)

    def _connect_postgres(self):
        return psycopg.connect(self.database_url, sslmode=("disable" if "sslmode=disable" in self.database_url else "require"), connect_timeout=15, row_factory=dict_row)

    def insert(self, row: dict[str, Any], lease: CollectorLease | None = None) -> None:
        if lease is not None and not self.database_url:
            raise ValueError("Collector leases require PostgreSQL-backed aggregate-trade storage")
        if self.database_url:
            with self._connect_postgres() as db:
                if lease is not None and not PostgresCollectorLease.lock_if_owned(db, lease):
                    raise CollectorLeaseLostError(
                        "Aggregate-trade write rejected because the collector lease is no longer owned"
                    )
                db.execute("""
                    INSERT INTO public.aggregate_trades (
                        market, symbol, trade_id, event_time_ms, trade_time_ms,
                        price, quantity, notional, buyer_is_maker, aggressor_side, raw_payload
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
                    ON CONFLICT(market, symbol, trade_id) DO NOTHING
                """, (
                    row["market"], row["symbol"], row["trade_id"], row["event_time_ms"],
                    row["trade_time_ms"], row["price"], row["quantity"], row["notional"],
                    row["buyer_is_maker"], row["aggressor_side"], row["raw_json"],
                ))
            return
        with sqlite3.connect(self.database_path) as db:
            db.execute("""
                INSERT OR IGNORE INTO aggregate_trades (
                    market, symbol, trade_id, event_time_ms, trade_time_ms,
                    price, quantity, notional, buyer_is_maker, aggressor_side, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                row["market"], row["symbol"], row["trade_id"], row["event_time_ms"],
                row["trade_time_ms"], row["price"], row["quantity"], row["notional"],
                int(row["buyer_is_maker"]), row["aggressor_side"], row["raw_json"],
            ))

    def recent(
        self, market: str, symbol: str, limit: int = 5000,
        start_time_ms: int | None = None, end_time_ms: int | None = None,
    ) -> list[dict[str, Any]]:
        if self.database_url:
            clauses = ["market=%s", "symbol=%s"]
            params: list[Any] = [market.upper(), symbol.upper()]
            if start_time_ms is not None:
                clauses.append("trade_time_ms >= %s"); params.append(start_time_ms)
            if end_time_ms is not None:
                clauses.append("trade_time_ms <= %s"); params.append(end_time_ms)
            params.append(limit)
            with self._connect_postgres() as db:
                rows = db.execute(
                    "SELECT market, symbol, trade_id, event_time_ms, trade_time_ms, price, quantity, "
                    "notional, buyer_is_maker, aggressor_side FROM public.aggregate_trades WHERE "
                    + " AND ".join(clauses) + " ORDER BY trade_time_ms DESC, trade_id DESC LIMIT %s", params,
                ).fetchall()
            result = [dict(row) for row in rows]
            for row in result:
                row["buyer_is_maker"] = bool(row["buyer_is_maker"])
            return result
        query = """SELECT market, symbol, trade_id, event_time_ms, trade_time_ms,
                   price, quantity, notional, buyer_is_maker, aggressor_side
                   FROM aggregate_trades WHERE market=? AND symbol=?"""
        params: list[Any] = [market.upper(), symbol.upper()]
        if start_time_ms is not None:
            query += " AND trade_time_ms >= ?"
            params.append(start_time_ms)
        if end_time_ms is not None:
            query += " AND trade_time_ms <= ?"
            params.append(end_time_ms)
        query += " ORDER BY trade_time_ms DESC, trade_id DESC LIMIT ?"
        params.append(limit)
        with sqlite3.connect(self.database_path) as db:
            db.row_factory = sqlite3.Row
            rows = [dict(row) for row in db.execute(query, params).fetchall()]
        for row in rows:
            row["buyer_is_maker"] = bool(row["buyer_is_maker"])
        return rows

    def count(self, market: str | None = None, symbol: str | None = None) -> int:
        if self.database_url:
            query = "SELECT COUNT(*) AS count FROM public.aggregate_trades WHERE 1=1"
            params: list[Any] = []
            if market:
                query += " AND market=%s"; params.append(market.upper())
            if symbol:
                query += " AND symbol=%s"; params.append(symbol.upper())
            with self._connect_postgres() as db:
                return int(db.execute(query, params).fetchone()["count"])
        query = "SELECT COUNT(*) FROM aggregate_trades WHERE 1=1"
        params: list[Any] = []
        if market:
            query += " AND market=?"
            params.append(market.upper())
        if symbol:
            query += " AND symbol=?"
            params.append(symbol.upper())
        with sqlite3.connect(self.database_path) as db:
            return int(db.execute(query, params).fetchone()[0])


class AggregateTradeCollector:
    def __init__(
        self, store: AggregateTradeStore, jobs_json: str = "[]",
        lease_database_url: str = "", lease_ttl_seconds: int = 30,
    ) -> None:
        self.store = store
        self.jobs_json = jobs_json
        self.lease_database_url = lease_database_url.strip()
        self.lease_ttl_seconds = lease_ttl_seconds
        if self.lease_database_url:
            PostgresCollectorLease(
                self.lease_database_url, "aggregate-trade:validation",
                ttl_seconds=lease_ttl_seconds,
            )
        self.tasks: list[asyncio.Task] = []
        self.states: dict[str, dict[str, Any]] = {}

    def _jobs(self) -> list[dict[str, str]]:
        try:
            raw = json.loads(self.jobs_json)
        except json.JSONDecodeError as exc:
            raise ValueError("AGG_TRADE_COLLECTOR_JOBS must be valid JSON") from exc
        if not isinstance(raw, list):
            raise ValueError("AGG_TRADE_COLLECTOR_JOBS must be a JSON array")
        jobs, seen = [], set()
        for item in raw:
            if not isinstance(item, dict):
                raise ValueError("Each agg-trade job must be an object")
            market = str(item.get("market", "")).upper()
            symbol = str(item.get("symbol", "")).strip().upper()
            if market not in {"SPOT", "USD_M", "COIN_M"} or not symbol or len(symbol) > 40:
                raise ValueError("Each job needs market SPOT/USD_M/COIN_M and a valid symbol")
            key = f"{market}:{symbol}"
            if key in seen:
                raise ValueError("Duplicate agg-trade collector job")
            seen.add(key)
            jobs.append({"market": market, "symbol": symbol})
        return jobs

    def start(self) -> None:
        if self.tasks:
            return
        self.tasks = [
            asyncio.create_task(self._run(job), name=f"agg-trades-{job['market']}-{job['symbol']}")
            for job in self._jobs()
        ]

    async def stop(self) -> None:
        tasks, self.tasks = self.tasks, []
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _persist_trade(
        self, row: dict[str, Any], lease_holder: dict[str, CollectorLease | None],
        lease_lost: asyncio.Event, state: dict[str, Any],
    ) -> None:
        try:
            await asyncio.to_thread(
                self.store.insert, row, lease_holder["lease"],
            )
        except CollectorLeaseLostError:
            lease_lost.set()
            state["lease_state"] = "LOST"
            state["last_error"] = "CollectorLeaseLostError"
            raise

    async def _renew_lease(
        self, manager: PostgresCollectorLease,
        lease_holder: dict[str, CollectorLease | None],
        lease_lost: asyncio.Event, state: dict[str, Any],
    ) -> None:
        interval = max(1.0, self.lease_ttl_seconds / 3)
        while not lease_lost.is_set():
            await asyncio.sleep(interval)
            lease = lease_holder["lease"]
            if lease is None:
                renewed = None
            else:
                try:
                    renewed = await asyncio.to_thread(manager.renew, lease)
                except Exception as exc:
                    state["last_error"] = type(exc).__name__
                    renewed = None
            if renewed is None:
                lease_lost.set()
                state["lease_state"] = "LOST"
                state["last_error"] = state.get("last_error") or "CollectorLeaseLostError"
                logger.error(
                    "Aggregate-trade lease lost for %s:%s; stopping permanently",
                    state["market"], state["symbol"],
                )
                return
            lease_holder["lease"] = renewed
            state["fencing_token"] = renewed.fencing_token

    async def _run_stream(
        self, market: str, symbol: str, state: dict[str, Any],
        lease_holder: dict[str, CollectorLease | None], lease_lost: asyncio.Event,
    ) -> None:
        delay = 1
        while not lease_lost.is_set():
            connection_started_at = None
            try:
                async with connect(
                    aggregate_trade_stream_url(market, symbol),
                    ping_interval=20, ping_timeout=20, close_timeout=10,
                ) as socket:
                    connection_started_at = asyncio.get_running_loop().time()
                    state.update(connected=True, last_error=None)
                    async for raw in socket:
                        if lease_lost.is_set():
                            return
                        payload = json.loads(raw)
                        row = normalize_aggregate_trade(payload, market)
                        if row is None or row["symbol"] != symbol:
                            continue
                        if lease_holder["lease"] is None:
                            await asyncio.to_thread(self.store.insert, row)
                        else:
                            await self._persist_trade(row, lease_holder, lease_lost, state)
                        state["received_count"] += 1
                        state["last_trade_at"] = datetime.now(timezone.utc).isoformat()
            except asyncio.CancelledError:
                raise
            except CollectorLeaseLostError:
                lease_lost.set()
                state["lease_state"] = "LOST"
                state["last_error"] = "CollectorLeaseLostError"
                return
            except Exception as exc:
                if lease_lost.is_set():
                    return
                if connection_started_at is not None and (
                    asyncio.get_running_loop().time() - connection_started_at >= 30
                ):
                    delay = 1
                state.update(
                    connected=False, last_error=type(exc).__name__,
                    reconnect_count=state["reconnect_count"] + 1,
                )
                logger.warning(
                    "Agg-trade stream %s:%s reconnecting after %s",
                    market, symbol, type(exc).__name__,
                )
                try:
                    await asyncio.wait_for(lease_lost.wait(), timeout=delay)
                except asyncio.TimeoutError:
                    pass
                delay = min(delay * 2, 60)
            else:
                # A clean WebSocket close ends async iteration without raising.
                # Preserve backoff for short-lived connections; reset it only
                # after a connection has remained healthy for at least 30s.
                if connection_started_at is not None and (
                    asyncio.get_running_loop().time() - connection_started_at >= 30
                ):
                    delay = 1
                if not lease_lost.is_set():
                    state.update(
                        connected=False, last_error="WebSocketClosed",
                        reconnect_count=state["reconnect_count"] + 1,
                    )
                    logger.warning(
                        "Agg-trade stream %s:%s closed; reconnecting after %ss",
                        market, symbol, delay,
                    )
                    try:
                        await asyncio.wait_for(lease_lost.wait(), timeout=delay)
                    except asyncio.TimeoutError:
                        pass
                    delay = min(delay * 2, 60)
            finally:
                state["connected"] = False

    async def _run(self, job: dict[str, str]) -> None:
        market, symbol = job["market"], job["symbol"]
        key = f"{market}:{symbol}"
        lease_name = f"aggregate-trade:{key}"
        state = self.states.setdefault(key, {
            "market": market, "symbol": symbol, "connected": False,
            "received_count": 0, "reconnect_count": 0, "last_trade_at": None,
            "last_error": None,
            "lease_state": "NOT_REQUIRED" if not self.lease_database_url else "WAITING",
            "lease_name": lease_name if self.lease_database_url else None,
            "fencing_token": None,
        })
        manager = (
            PostgresCollectorLease(
                self.lease_database_url, lease_name,
                ttl_seconds=self.lease_ttl_seconds,
            ) if self.lease_database_url else None
        )
        lease_holder: dict[str, CollectorLease | None] = {"lease": None}
        lease_lost = asyncio.Event()
        heartbeat: asyncio.Task | None = None
        stream: asyncio.Task | None = None
        try:
            if manager is not None:
                while lease_holder["lease"] is None:
                    worker = asyncio.create_task(asyncio.to_thread(manager.acquire))
                    try:
                        lease = await asyncio.shield(worker)
                    except asyncio.CancelledError:
                        try:
                            acquired_during_shutdown = await worker
                            if acquired_during_shutdown is not None:
                                await asyncio.to_thread(manager.release, acquired_during_shutdown)
                        except Exception as exc:
                            state["last_error"] = type(exc).__name__
                        raise
                    except Exception as exc:
                        state["lease_state"] = "ACQUIRE_FAILED"
                        state["last_error"] = type(exc).__name__
                        await asyncio.sleep(10)
                        continue
                    if lease is None:
                        state["lease_state"] = "HELD_BY_OTHER"
                        await asyncio.sleep(1)
                        continue
                    lease_holder["lease"] = lease
                    state.update(lease_state="ACTIVE", fencing_token=lease.fencing_token)
                heartbeat = asyncio.create_task(
                    self._renew_lease(manager, lease_holder, lease_lost, state),
                    name=f"aggregate-trade-lease-{key}",
                )

            stream = asyncio.create_task(
                self._run_stream(market, symbol, state, lease_holder, lease_lost),
                name=f"aggregate-trade-stream-{key}",
            )
            if heartbeat is None:
                await stream
            else:
                done, pending = await asyncio.wait(
                    {stream, heartbeat}, return_when=asyncio.FIRST_COMPLETED,
                )
                for task in pending:
                    task.cancel()
                await asyncio.gather(*pending, return_exceptions=True)
                for task in done:
                    exception = task.exception()
                    if exception is not None:
                        raise exception
                if lease_lost.is_set():
                    state["lease_state"] = "LOST"
        finally:
            if stream is not None and not stream.done():
                stream.cancel()
            if stream is not None:
                await asyncio.gather(stream, return_exceptions=True)
            if heartbeat is not None:
                if not heartbeat.done():
                    heartbeat.cancel()
                await asyncio.gather(heartbeat, return_exceptions=True)
            lease = lease_holder["lease"]
            if manager is not None and lease is not None and not lease_lost.is_set():
                try:
                    released = await asyncio.shield(asyncio.to_thread(manager.release, lease))
                    state["lease_state"] = "RELEASED" if released else "RELEASE_FAILED"
                except Exception as exc:
                    state["lease_state"] = "RELEASE_FAILED"
                    state["last_error"] = type(exc).__name__
                    logger.exception("Failed to release aggregate-trade lease for %s", key)

    def status(self) -> dict[str, Any]:
        return {
            "enabled": True, "job_count": len(self.states),
            "jobs": list(self.states.values()),
            "stored_trade_count": self.store.count(),
            "warning": (
                "PostgreSQL leases coordinate each configured market/symbol stream; "
                "SQLite-backed collection remains single-process-only. No earlier trade history is backfilled."
            ),
        }
