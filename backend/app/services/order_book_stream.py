from __future__ import annotations

import asyncio
import json
import logging
import math
import sqlite3
from decimal import Decimal, InvalidOperation
import psycopg
from psycopg.rows import dict_row
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote

from websockets.asyncio.client import connect

logger = logging.getLogger(__name__)


def depth_stream_url(market: str, symbol: str) -> str:
    market = market.upper()
    symbol = symbol.lower()
    if market == "SPOT":
        return f"wss://stream.binance.com:9443/ws/{quote(symbol, safe='')}@depth@100ms"
    if market == "USD_M":
        return f"wss://fstream.binance.com/public/ws/{quote(symbol, safe='')}@depth@100ms"
    if market == "COIN_M":
        return f"wss://dstream.binance.com/ws/{quote(symbol, safe='')}@depth@100ms"
    raise ValueError("market must be SPOT, USD_M or COIN_M")


class OrderBookHistoryStore:
    def __init__(self, database_path: str, database_url: str = "") -> None:
        self.database_path = database_path
        self.database_url = database_url.strip()
        if self.database_url:
            return
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(database_path) as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS order_book_samples (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    market TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    event_time_ms INTEGER,
                    transaction_time_ms INTEGER,
                    update_id INTEGER NOT NULL,
                    sampled_at TEXT NOT NULL,
                    best_bid REAL NOT NULL,
                    best_ask REAL NOT NULL,
                    mid_price REAL NOT NULL,
                    spread_bps REAL NOT NULL,
                    bid_notional REAL NOT NULL,
                    ask_notional REAL NOT NULL,
                    depth_imbalance REAL NOT NULL,
                    bids_json TEXT NOT NULL,
                    asks_json TEXT NOT NULL,
                    UNIQUE(market, symbol, update_id)
                )
            """)
            db.execute("""
                CREATE INDEX IF NOT EXISTS idx_order_book_samples_market_symbol_time
                ON order_book_samples(market, symbol, event_time_ms)
            """)

    def _connect_postgres(self):
        return psycopg.connect(self.database_url, sslmode=("disable" if "sslmode=disable" in self.database_url else "require"), connect_timeout=15, row_factory=dict_row)

    @staticmethod
    def _validated_row(row: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(row, dict):
            raise ValueError("order-book sample must be an object")
        required = {
            "market", "symbol", "update_id", "sampled_at", "best_bid", "best_ask",
            "mid_price", "spread_bps", "bid_notional", "ask_notional",
            "depth_imbalance", "bids", "asks",
        }
        if not required.issubset(row):
            raise ValueError("order-book sample is missing required fields")
        market = row["market"]
        symbol = row["symbol"]
        if not isinstance(market, str) or market not in {"SPOT", "USD_M", "COIN_M"}:
            raise ValueError("Invalid order-book market")
        if not isinstance(symbol, str) or not symbol.strip() or len(symbol) > 40:
            raise ValueError("Invalid order-book symbol")
        if not isinstance(row["sampled_at"], str) or not row["sampled_at"].strip():
            raise ValueError("Invalid order-book sample timestamp")

        def integer(value: Any, field: str, optional: bool = False) -> int | None:
            if value is None and optional:
                return None
            if isinstance(value, bool):
                raise ValueError(f"Invalid order-book {field}")
            try:
                number = Decimal(str(value))
            except (InvalidOperation, TypeError, ValueError):
                raise ValueError(f"Invalid order-book {field}") from None
            if not number.is_finite() or number != number.to_integral_value() or number < 0:
                raise ValueError(f"Invalid order-book {field}")
            return int(number)

        def finite(value: Any, field: str) -> float:
            if isinstance(value, bool):
                raise ValueError(f"Invalid order-book {field}")
            try:
                number = float(value)
            except (TypeError, ValueError, OverflowError):
                raise ValueError(f"Invalid order-book {field}") from None
            if not math.isfinite(number):
                raise ValueError(f"Invalid order-book {field}")
            return number

        validated: dict[str, Any] = dict(row)
        validated["update_id"] = integer(row["update_id"], "update ID")
        validated["event_time_ms"] = integer(row.get("event_time_ms"), "event time", optional=True)
        validated["transaction_time_ms"] = integer(row.get("transaction_time_ms"), "transaction time", optional=True)
        for field in ("best_bid", "best_ask", "mid_price", "spread_bps",
                      "bid_notional", "ask_notional", "depth_imbalance"):
            validated[field] = finite(row[field], field)
        if (validated["best_bid"] <= 0 or validated["best_ask"] <= validated["best_bid"]
                or validated["mid_price"] <= 0 or validated["spread_bps"] < 0
                or validated["bid_notional"] < 0 or validated["ask_notional"] < 0
                or not -1 <= validated["depth_imbalance"] <= 1):
            raise ValueError("Invalid order-book sample metrics")

        for side, descending in (("bids", True), ("asks", False)):
            levels = row[side]
            if not isinstance(levels, list) or not 1 <= len(levels) <= 1000:
                raise ValueError(f"Invalid order-book {side}")
            normalized = []
            previous = None
            for level in levels:
                if not isinstance(level, (list, tuple)) or len(level) != 2:
                    raise ValueError(f"Invalid order-book {side} level")
                price = finite(level[0], f"{side} price")
                quantity = finite(level[1], f"{side} quantity")
                if price <= 0 or quantity < 0:
                    raise ValueError(f"Invalid order-book {side} level")
                if previous is not None and ((descending and price >= previous) or (not descending and price <= previous)):
                    raise ValueError(f"Unsorted order-book {side}")
                previous = price
                normalized.append([price, quantity])
            validated[side] = normalized
        if (validated["bids"][0][0] != validated["best_bid"]
                or validated["asks"][0][0] != validated["best_ask"]):
            raise ValueError("Order-book best prices do not match stored levels")
        return validated

    def insert(self, row: dict[str, Any]) -> None:
        row = self._validated_row(row)
        if self.database_url:
            with self._connect_postgres() as db:
                db.execute("""
                    INSERT INTO public.order_book_samples (
                        market, symbol, event_time_ms, transaction_time_ms, update_id,
                        sampled_at, best_bid, best_ask, mid_price, spread_bps,
                        bid_notional, ask_notional, depth_imbalance, bids, asks
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb)
                    ON CONFLICT(market, symbol, update_id) DO NOTHING
                """, (
                    row["market"], row["symbol"], row.get("event_time_ms"),
                    row.get("transaction_time_ms"), row["update_id"], row["sampled_at"],
                    row["best_bid"], row["best_ask"], row["mid_price"], row["spread_bps"],
                    row["bid_notional"], row["ask_notional"], row["depth_imbalance"],
                    json.dumps(row["bids"], separators=(",", ":")),
                    json.dumps(row["asks"], separators=(",", ":")),
                ))
            return
        with sqlite3.connect(self.database_path) as db:
            db.execute("""
                INSERT OR IGNORE INTO order_book_samples (
                    market, symbol, event_time_ms, transaction_time_ms, update_id,
                    sampled_at, best_bid, best_ask, mid_price, spread_bps,
                    bid_notional, ask_notional, depth_imbalance, bids_json, asks_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                row["market"], row["symbol"], row.get("event_time_ms"),
                row.get("transaction_time_ms"), row["update_id"], row["sampled_at"],
                row["best_bid"], row["best_ask"], row["mid_price"], row["spread_bps"],
                row["bid_notional"], row["ask_notional"], row["depth_imbalance"],
                json.dumps(row["bids"], separators=(",", ":")),
                json.dumps(row["asks"], separators=(",", ":")),
            ))

    @staticmethod
    def _query_integer(value: Any, field: str, *, minimum: int = 0) -> int:
        if isinstance(value, bool):
            raise ValueError(f"Invalid order-book {field}")
        try:
            number = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            raise ValueError(f"Invalid order-book {field}") from None
        if not number.is_finite() or number != number.to_integral_value() or number < minimum:
            raise ValueError(f"Invalid order-book {field}")
        return int(number)

    @staticmethod
    def _validate_query_market_symbol(market: Any, symbol: Any) -> tuple[str, str]:
        if not isinstance(market, str) or market.upper() not in {"SPOT", "USD_M", "COIN_M"}:
            raise ValueError("Invalid order-book market")
        if not isinstance(symbol, str) or not symbol.strip() or len(symbol) > 40:
            raise ValueError("Invalid order-book symbol")
        return market.upper(), symbol.upper()

    def recent(
        self, market: str, symbol: str, limit: int = 100,
        start_time_ms: int | None = None, end_time_ms: int | None = None,
    ) -> list[dict[str, Any]]:
        market, symbol = self._validate_query_market_symbol(market, symbol)
        limit = self._query_integer(limit, "query limit", minimum=1)
        if limit > 10000:
            raise ValueError("Invalid order-book query limit")
        if start_time_ms is not None:
            start_time_ms = self._query_integer(start_time_ms, "start time")
        if end_time_ms is not None:
            end_time_ms = self._query_integer(end_time_ms, "end time")
        if start_time_ms is not None and end_time_ms is not None and start_time_ms > end_time_ms:
            raise ValueError("Invalid order-book time range")
        if self.database_url:
            clauses = ["market=%s", "symbol=%s"]
            params: list[Any] = [market, symbol]
            if start_time_ms is not None:
                clauses.append("event_time_ms >= %s"); params.append(start_time_ms)
            if end_time_ms is not None:
                clauses.append("event_time_ms <= %s"); params.append(end_time_ms)
            params.append(limit)
            with self._connect_postgres() as db:
                rows = db.execute(
                    "SELECT market, symbol, event_time_ms, transaction_time_ms, update_id, sampled_at, "
                    "best_bid, best_ask, mid_price, spread_bps, bid_notional, ask_notional, depth_imbalance, "
                    "bids, asks FROM public.order_book_samples WHERE " + " AND ".join(clauses) +
                    " ORDER BY event_time_ms DESC, update_id DESC LIMIT %s", params,
                ).fetchall()
            result = []
            for row in rows:
                item = dict(row)
                item["bids"] = item["bids"] if isinstance(item["bids"], list) else json.loads(item["bids"])
                item["asks"] = item["asks"] if isinstance(item["asks"], list) else json.loads(item["asks"])
                result.append(item)
            return result
        query = """SELECT market, symbol, event_time_ms, transaction_time_ms,
                   update_id, sampled_at, best_bid, best_ask, mid_price, spread_bps,
                   bid_notional, ask_notional, depth_imbalance, bids_json, asks_json
                   FROM order_book_samples WHERE market=? AND symbol=?"""
        params: list[Any] = [market, symbol]
        if start_time_ms is not None:
            query += " AND event_time_ms >= ?"
            params.append(start_time_ms)
        if end_time_ms is not None:
            query += " AND event_time_ms <= ?"
            params.append(end_time_ms)
        query += " ORDER BY event_time_ms DESC, id DESC LIMIT ?"
        params.append(limit)
        with sqlite3.connect(self.database_path) as db:
            db.row_factory = sqlite3.Row
            rows = [dict(row) for row in db.execute(query, params).fetchall()]
        for row in rows:
            row["bids"] = json.loads(row.pop("bids_json"))
            row["asks"] = json.loads(row.pop("asks_json"))
        return rows

    def count(self, market: str | None = None, symbol: str | None = None) -> int:
        if market is not None and (not isinstance(market, str) or market.upper() not in {"SPOT", "USD_M", "COIN_M"}):
            raise ValueError("Invalid order-book market")
        if market is not None:
            market = market.upper()
        if symbol is not None and (not isinstance(symbol, str) or not symbol.strip() or len(symbol) > 40):
            raise ValueError("Invalid order-book symbol")
        if self.database_url:
            query = "SELECT COUNT(*) AS count FROM public.order_book_samples WHERE 1=1"
            params: list[Any] = []
            if market is not None:
                query += " AND market=%s"; params.append(market)
            if symbol is not None:
                query += " AND symbol=%s"; params.append(symbol.upper())
            with self._connect_postgres() as db:
                return int(db.execute(query, params).fetchone()["count"])
        query = "SELECT COUNT(*) FROM order_book_samples WHERE 1=1"
        params: list[Any] = []
        if market is not None:
            query += " AND market=?"
            params.append(market)
        if symbol is not None:
            query += " AND symbol=?"
            params.append(symbol.upper())
        with sqlite3.connect(self.database_path) as db:
            return int(db.execute(query, params).fetchone()[0])


class OrderBookStreamCollector:
    """Sequence-aware local depth builder; one process should own each configured job."""

    def __init__(
        self, store: OrderBookHistoryStore,
        spot_provider_factory: Callable[[], Any],
        futures_provider_factory: Callable[[str], Any],
        jobs_json: str = "[]", sample_interval_seconds: float = 1.0,
        snapshot_limit: int = 1000, stored_levels: int = 20,
    ) -> None:
        self.store = store
        self.spot_provider_factory = spot_provider_factory
        self.futures_provider_factory = futures_provider_factory
        self.jobs_json = jobs_json
        self.sample_interval_seconds = sample_interval_seconds
        self.snapshot_limit = snapshot_limit
        if sample_interval_seconds <= 0:
            raise ValueError("sample_interval_seconds must be positive")
        if not 1 <= snapshot_limit <= 1000:
            raise ValueError("snapshot_limit must be between 1 and 1000")
        if not 1 <= stored_levels <= snapshot_limit:
            raise ValueError("stored_levels must be between 1 and snapshot_limit")
        self.stored_levels = stored_levels
        self.tasks: list[asyncio.Task] = []
        self.states: dict[str, dict[str, Any]] = {}
        self._stop = asyncio.Event()

    def _jobs(self) -> list[dict[str, str]]:
        try:
            raw = json.loads(self.jobs_json)
        except json.JSONDecodeError as exc:
            raise ValueError("ORDER_BOOK_COLLECTOR_JOBS must be valid JSON") from exc
        if not isinstance(raw, list):
            raise ValueError("ORDER_BOOK_COLLECTOR_JOBS must be a JSON array")
        jobs = []
        seen = set()
        for item in raw:
            if not isinstance(item, dict):
                raise ValueError("Each order-book collector job must be an object")
            market = str(item.get("market", "")).upper()
            symbol = str(item.get("symbol", "")).strip().upper()
            if market not in {"SPOT", "USD_M", "COIN_M"} or not symbol or len(symbol) > 40:
                raise ValueError("Each job needs market SPOT/USD_M/COIN_M and a valid symbol")
            key = f"{market}:{symbol}"
            if key in seen:
                raise ValueError("Duplicate order-book collector job")
            seen.add(key)
            jobs.append({"market": market, "symbol": symbol})
        return jobs

    def start(self) -> None:
        if self.tasks:
            return
        self._stop.clear()
        self.tasks = [
            asyncio.create_task(self._run_job(job), name=f"order-book-{job['market']}-{job['symbol']}")
            for job in self._jobs()
        ]

    async def stop(self) -> None:
        self._stop.set()
        for task in self.tasks:
            task.cancel()
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks = []

    def _provider(self, market: str) -> Any:
        return self.spot_provider_factory() if market == "SPOT" else self.futures_provider_factory(market)

    async def _reader(self, socket: Any, queue: asyncio.Queue) -> None:
        try:
            async for raw in socket:
                await queue.put(json.loads(raw))
        finally:
            try:
                queue.put_nowait(None)
            except asyncio.QueueFull:
                pass

    async def _run_job(self, job: dict[str, str]) -> None:
        market, symbol = job["market"], job["symbol"]
        key = f"{market}:{symbol}"
        state = self.states.setdefault(key, {
            "market": market, "symbol": symbol, "connected": False,
            "synchronized": False, "stored_count": 0, "reconnect_count": 0,
            "last_event_at": None, "last_error": None,
        })
        delay = 1
        while not self._stop.is_set():
            try:
                url = depth_stream_url(market, symbol)
                async with connect(url, ping_interval=20, ping_timeout=20, close_timeout=10) as socket:
                    state.update(connected=True, synchronized=False, last_error=None)
                    queue: asyncio.Queue = asyncio.Queue(maxsize=20000)
                    reader = asyncio.create_task(self._reader(socket, queue))
                    try:
                        snapshot = await self._provider(market).order_book(symbol, self.snapshot_limit)
                        last_id = self._strict_integer(snapshot["lastUpdateId"], "snapshot update ID")
                        bids = self._levels(snapshot["bids"])
                        asks = self._levels(snapshot["asks"])
                        first_event = True
                        # Discard stale buffered updates, then bridge the snapshot update ID.
                        while not queue.empty():
                            event = queue.get_nowait()
                            if event is None:
                                raise RuntimeError("DEPTH_STREAM_CLOSED_DURING_SYNC")
                            if self._strict_integer(event.get("u", 0), "final update ID") <= last_id:
                                continue
                            self._validate_sequence(market, event, last_id, first_event)
                            self._apply(event, bids, asks)
                            self._trim_book(bids, asks)
                            last_id = self._strict_integer(event["u"], "final update ID")
                            first_event = False
                        state["synchronized"] = not first_event
                        delay = 1
                        last_sample = 0.0
                        import time
                        while not self._stop.is_set():
                            event = await queue.get()
                            if event is None:
                                raise RuntimeError("DEPTH_STREAM_CLOSED")
                            final_id = self._strict_integer(event.get("u", 0), "final update ID")
                            if final_id <= last_id:
                                continue
                            self._validate_sequence(market, event, last_id, first_event)
                            self._apply(event, bids, asks)
                            self._trim_book(bids, asks)
                            last_id = final_id
                            first_event = False
                            state["synchronized"] = True
                            state["last_event_at"] = datetime.now(timezone.utc).isoformat()
                            now = time.monotonic()
                            if now - last_sample >= self.sample_interval_seconds:
                                row = self._sample(market, symbol, event, last_id, bids, asks)
                                if row is not None:
                                    await asyncio.to_thread(self.store.insert, row)
                                    state["stored_count"] += 1
                                    last_sample = now
                    finally:
                        reader.cancel()
                        await asyncio.gather(reader, return_exceptions=True)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                state.update(connected=False, synchronized=False,
                             last_error=type(exc).__name__, reconnect_count=state["reconnect_count"] + 1)
                logger.warning("Order-book stream %s reconnecting after %s", key, type(exc).__name__)
                await asyncio.sleep(delay)
                delay = min(delay * 2, 60)
            finally:
                state["connected"] = False
                state["synchronized"] = False

    @staticmethod
    def _strict_integer(value: Any, field: str) -> int:
        if isinstance(value, bool):
            raise ValueError(f"Invalid order-book {field}")
        try:
            number = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValueError(f"Invalid order-book {field}") from exc
        if not number.is_finite() or number != number.to_integral_value():
            raise ValueError(f"Invalid order-book {field}")
        return int(number)

    @staticmethod
    def _validate_sequence(market: str, event: dict[str, Any], last_id: int, first_event: bool) -> None:
        try:
            first_id = OrderBookStreamCollector._strict_integer(event.get("U", 0), "first update ID")
            final_id = OrderBookStreamCollector._strict_integer(event.get("u", 0), "final update ID")
            previous_id = event.get("pu")
            if final_id < first_id:
                raise ValueError("Invalid order-book update range")
            if first_event:
                if not (first_id <= last_id + 1 <= final_id):
                    raise RuntimeError("DEPTH_INITIAL_SEQUENCE_GAP")
                return
            if market in {"USD_M", "COIN_M"}:
                if previous_id is None or OrderBookStreamCollector._strict_integer(previous_id, "previous update ID") != last_id:
                    raise RuntimeError("DEPTH_SEQUENCE_GAP")
            elif first_id > last_id + 1:
                raise RuntimeError("DEPTH_SEQUENCE_GAP")
        except (TypeError, ValueError) as exc:
            raise RuntimeError("DEPTH_INVALID_SEQUENCE") from exc

    def _trim_book(self, bids: dict[float, float], asks: dict[float, float]) -> None:
        if len(bids) > self.snapshot_limit:
            for price in sorted(bids)[:-self.snapshot_limit]:
                bids.pop(price, None)
        if len(asks) > self.snapshot_limit:
            for price in sorted(asks, reverse=True)[:-self.snapshot_limit]:
                asks.pop(price, None)
    @staticmethod
    def _levels(levels: Any) -> dict[float, float]:
        """Validate an exchange snapshot side before admitting it into the book."""
        if not isinstance(levels, list):
            raise ValueError("Invalid order-book levels")
        normalized: dict[float, float] = {}
        for level in levels:
            if not isinstance(level, (list, tuple)) or len(level) != 2:
                raise ValueError("Invalid order-book level")
            try:
                price, quantity = float(level[0]), float(level[1])
            except (TypeError, ValueError, OverflowError) as exc:
                raise ValueError("Invalid order-book level") from exc
            if not math.isfinite(price) or not math.isfinite(quantity) or price <= 0 or quantity < 0:
                raise ValueError("Order-book price and quantity must be finite; price positive and quantity non-negative")
            if quantity > 0:
                normalized[price] = quantity
        return normalized

    @staticmethod
    def _apply(event: dict[str, Any], bids: dict[float, float], asks: dict[float, float]) -> None:
        if not isinstance(event, dict):
            raise ValueError("Invalid order-book event")
        for key, book_side in (("b", bids), ("a", asks)):
            raw_levels = event.get(key, [])
            if not isinstance(raw_levels, list):
                raise ValueError("Invalid order-book levels")
            parsed = []
            for level in raw_levels:
                if not isinstance(level, (list, tuple)) or len(level) != 2:
                    raise ValueError("Invalid order-book level")
                try:
                    price, quantity = float(level[0]), float(level[1])
                except (TypeError, ValueError, OverflowError) as exc:
                    raise ValueError("Invalid order-book level") from exc
                if not math.isfinite(price) or not math.isfinite(quantity) or price <= 0 or quantity < 0:
                    raise ValueError("Order-book price and quantity must be finite; price positive and quantity non-negative")
                parsed.append((price, quantity))
            for price, quantity in parsed:
                if quantity == 0:
                    book_side.pop(price, None)
                else:
                    book_side[price] = quantity

    def _sample(
        self, market: str, symbol: str, event: dict[str, Any], update_id: int,
        bids: dict[float, float], asks: dict[float, float],
    ) -> dict[str, Any] | None:
        if not isinstance(event, dict):
            raise ValueError("Invalid order-book event")
        update_id = self._strict_integer(update_id, "update ID")
        if update_id < 0:
            raise ValueError("Invalid order-book update ID")
        event_time = event.get("E")
        transaction_time = event.get("T")
        if event_time is not None:
            event_time = self._strict_integer(event_time, "event time")
            if event_time < 0:
                raise ValueError("Invalid order-book event time")
        if transaction_time is not None:
            transaction_time = self._strict_integer(transaction_time, "transaction time")
            if transaction_time < 0:
                raise ValueError("Invalid order-book transaction time")
        bid_rows = sorted(bids.items(), reverse=True)[:self.stored_levels]
        ask_rows = sorted(asks.items())[:self.stored_levels]
        if not bid_rows or not ask_rows or bid_rows[0][0] >= ask_rows[0][0]:
            return None
        bid_notional = sum(p * q for p, q in bid_rows)
        ask_notional = sum(p * q for p, q in ask_rows)
        total = bid_notional + ask_notional
        mid = bid_rows[0][0] / 2 + ask_rows[0][0] / 2
        spread_bps = (ask_rows[0][0] - bid_rows[0][0]) / mid * 10000
        depth_imbalance = (bid_notional - ask_notional) / total if total else 0.0
        derived = (bid_notional, ask_notional, total, mid, spread_bps, depth_imbalance)
        if not all(math.isfinite(value) for value in derived) or total <= 0 or mid <= 0:
            # Skip pathological finite inputs whose derived notionals overflow IEEE-754.
            return None
        return {
            "market": market, "symbol": symbol,
            "event_time_ms": event_time, "transaction_time_ms": transaction_time,
            "update_id": update_id, "sampled_at": datetime.now(timezone.utc).isoformat(),
            "best_bid": bid_rows[0][0], "best_ask": ask_rows[0][0], "mid_price": mid,
            "spread_bps": spread_bps,
            "bid_notional": bid_notional, "ask_notional": ask_notional,
            "depth_imbalance": depth_imbalance,
            "bids": bid_rows, "asks": ask_rows,
        }

    def status(self) -> dict[str, Any]:
        jobs = list(self.states.values())
        connected = sum(1 for job in jobs if job.get("connected"))
        task_count = len(self.tasks)
        if task_count == 0:
            status = "IDLE"
        elif not jobs:
            status = "STARTING"
        elif connected == len(jobs):
            status = "RUNNING"
        elif any(job.get("last_error") for job in jobs):
            status = "DEGRADED"
        else:
            status = "CONNECTING"
        return {
            "status": status,
            "enabled": True,
            "job_count": task_count,
            "active_task_count": sum(1 for task in self.tasks if not task.done()),
            "connected_job_count": connected,
            "disconnected_job_count": max(0, len(jobs) - connected),
            "jobs": jobs,
            "stored_sample_count": self.store.count(),
            "warning": "Depth samples are locally captured after sequence synchronization; collection begins after deployment and is not backfilled.",
        }
