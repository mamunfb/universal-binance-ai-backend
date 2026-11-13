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
    if payload.get("e") != "aggTrade":
        return None
    try:
        normalized_market = market.upper()
        if normalized_market not in {"SPOT", "USD_M", "COIN_M"}:
            return None
        symbol = str(payload["s"]).strip().upper()
        if not symbol or len(symbol) > 40:
            return None
        raw_trade_id = payload["a"]
        raw_event_time = payload["E"]
        raw_trade_time = payload["T"]
        if any(isinstance(value, bool) for value in (raw_trade_id, raw_event_time, raw_trade_time)):
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

    def insert(self, row: dict[str, Any]) -> None:
        if self.database_url:
            with self._connect_postgres() as db:
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
    def __init__(self, store: AggregateTradeStore, jobs_json: str = "[]") -> None:
        self.store = store
        self.jobs_json = jobs_json
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
        for task in self.tasks:
            task.cancel()
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks = []

    async def _run(self, job: dict[str, str]) -> None:
        market, symbol = job["market"], job["symbol"]
        key = f"{market}:{symbol}"
        state = self.states.setdefault(key, {
            "market": market, "symbol": symbol, "connected": False,
            "received_count": 0, "reconnect_count": 0, "last_trade_at": None,
            "last_error": None,
        })
        delay = 1
        while True:
            try:
                async with connect(
                    aggregate_trade_stream_url(market, symbol),
                    ping_interval=20, ping_timeout=20, close_timeout=10,
                ) as socket:
                    state.update(connected=True, last_error=None)
                    delay = 1
                    async for raw in socket:
                        payload = json.loads(raw)
                        row = normalize_aggregate_trade(payload, market)
                        if row is None or row["symbol"] != symbol:
                            continue
                        await asyncio.to_thread(self.store.insert, row)
                        state["received_count"] += 1
                        state["last_trade_at"] = datetime.now(timezone.utc).isoformat()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                state.update(connected=False, last_error=type(exc).__name__,
                             reconnect_count=state["reconnect_count"] + 1)
                logger.warning("Agg-trade stream %s reconnecting after %s", key, type(exc).__name__)
                await asyncio.sleep(delay)
                delay = min(delay * 2, 60)
            finally:
                state["connected"] = False

    def status(self) -> dict[str, Any]:
        return {
            "enabled": True, "job_count": len(self.states),
            "jobs": list(self.states.values()),
            "stored_trade_count": self.store.count(),
            "warning": "Aggregate trade collection starts on enablement; no earlier trade history is backfilled.",
        }
