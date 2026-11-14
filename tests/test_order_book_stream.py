import json
import sqlite3

import pytest

from app.services.order_book_stream import (
    OrderBookHistoryStore,
    OrderBookStreamCollector,
    depth_stream_url,
)


def test_depth_stream_urls_for_all_markets():
    assert "stream.binance.com" in depth_stream_url("SPOT", "BTCUSDT")
    assert "fstream.binance.com" in depth_stream_url("USD_M", "BTCUSDT")
    assert "dstream.binance.com" in depth_stream_url("COIN_M", "BTCUSD_PERP")
    with pytest.raises(ValueError):
        depth_stream_url("UNKNOWN", "BTCUSDT")


def test_history_store_is_idempotent_and_filters(tmp_path):
    store = OrderBookHistoryStore(str(tmp_path / "book.sqlite3"))
    row = {
        "market": "USD_M", "symbol": "BTCUSDT", "event_time_ms": 1000,
        "transaction_time_ms": 1000, "update_id": 12, "sampled_at": "2026-01-01T00:00:00+00:00",
        "best_bid": 99.0, "best_ask": 101.0, "mid_price": 100.0,
        "spread_bps": 200.0, "bid_notional": 990.0, "ask_notional": 101.0,
        "depth_imbalance": 0.8, "bids": [[99.0, 10.0]], "asks": [[101.0, 1.0]],
    }
    store.insert(row)
    store.insert(row)
    assert store.count() == 1
    result = store.recent("USD_M", "btcusdt", 10)
    assert len(result) == 1
    assert result[0]["bids"] == [[99.0, 10.0]]
    assert store.recent("SPOT", "BTCUSDT", 10) == []


def test_order_book_store_rejects_lease_with_sqlite_storage(tmp_path):
    store = OrderBookHistoryStore(str(tmp_path / "book.sqlite3"))
    with pytest.raises(ValueError, match="PostgreSQL"):
        store.insert({"market": "SPOT", "symbol": "BTCUSDT"}, lease=object())


def test_collector_job_validation_and_book_delta_application(tmp_path):
    store = OrderBookHistoryStore(str(tmp_path / "book.sqlite3"))
    collector = OrderBookStreamCollector(
        store, lambda: None, lambda market: None,
        jobs_json=json.dumps([{"market": "USD_M", "symbol": "BTCUSDT"}]),
    )
    jobs = collector._jobs()
    assert jobs == [{"market": "USD_M", "symbol": "BTCUSDT"}]
    bids, asks = {100.0: 2.0}, {101.0: 3.0}
    collector._apply({"b": [["100", "0"], ["99.5", "4"]], "a": [["101", "5"]]}, bids, asks)
    assert bids == {99.5: 4.0}
    assert asks == {101.0: 5.0}
    with pytest.raises(ValueError):
        OrderBookStreamCollector(
            store, lambda: None, lambda market: None, jobs_json="not-json"
        )._jobs()


def test_sample_calculates_spread_and_depth(tmp_path):
    collector = OrderBookStreamCollector(
        OrderBookHistoryStore(str(tmp_path / "book.sqlite3")),
        lambda: None, lambda market: None, stored_levels=2,
    )
    row = collector._sample(
        "SPOT", "BTCUSDT", {"E": 10, "T": 9}, 15,
        {100.0: 2.0, 99.0: 3.0}, {101.0: 1.0, 102.0: 4.0},
    )
    assert row is not None
    assert row["best_bid"] == 100.0
    assert row["best_ask"] == 101.0
    assert row["spread_bps"] > 0
    assert row["depth_imbalance"] < 0  # Ask-side price-weighted notional exceeds bid-side notional.



def test_order_book_collector_validates_lease_ttl_before_start(tmp_path):
    store = OrderBookHistoryStore(str(tmp_path / "book.sqlite3"))
    with pytest.raises(ValueError, match="ttl_seconds"):
        OrderBookStreamCollector(
            store, lambda: None, lambda market: None,
            lease_database_url="postgresql://example/db",
            lease_ttl_seconds=2,
        )


def test_order_book_job_waits_for_stable_market_symbol_lease(tmp_path, monkeypatch):
    import asyncio
    from app.services import order_book_stream

    captured = {}

    class FakeLeaseManager:
        def __init__(self, database_url, lease_name, ttl_seconds):
            captured.update(database_url=database_url, lease_name=lease_name, ttl_seconds=ttl_seconds)

        def acquire(self):
            captured["acquired"] = True
            return None

    monkeypatch.setattr(order_book_stream, "PostgresCollectorLease", FakeLeaseManager)
    collector = OrderBookStreamCollector(
        OrderBookHistoryStore(str(tmp_path / "book.sqlite3")),
        lambda: None, lambda market: None,
        jobs_json=json.dumps([{"market": "USD_M", "symbol": "BTCUSDT"}]),
        lease_database_url="postgresql://example/db",
        lease_ttl_seconds=45,
    )

    async def run_and_stop():
        task = asyncio.create_task(collector._run_job(collector._jobs()[0]))
        await asyncio.sleep(0)
        collector._stop.set()
        await task

    asyncio.run(run_and_stop())
    assert captured == {
        "database_url": "postgresql://example/db",
        "lease_name": "order-book:USD_M:BTCUSDT",
        "ttl_seconds": 45,
        "acquired": True,
    }


def test_order_book_waits_for_inflight_insert_before_releasing_lease(monkeypatch, tmp_path):
    import asyncio
    import json
    import threading
    from types import SimpleNamespace
    from app.services import order_book_stream as module

    insert_started = threading.Event()
    finish_insert = threading.Event()
    released = []
    lease = SimpleNamespace(fencing_token=51)

    class FakeLeaseManager:
        def __init__(self, *_args, **_kwargs):
            pass

        def acquire(self):
            return lease

        def renew(self, current):
            return current

        def release(self, current):
            released.append(current)
            return True

    class BlockingStore:
        def insert(self, _row, current_lease=None):
            assert current_lease is lease
            insert_started.set()
            if not finish_insert.wait(timeout=3):
                raise TimeoutError("test insert was not released")

    class Provider:
        async def order_book(self, _symbol, _limit):
            return {
                "lastUpdateId": 100,
                "bids": [["99", "1"]],
                "asks": [["101", "1"]],
            }

    class Socket:
        def __aiter__(self):
            async def iterate():
                yield json.dumps({
                    "U": 101, "u": 101, "E": 1700000000123, "T": 1700000000100,
                    "b": [["99", "2"]], "a": [["101", "1"]],
                })
                await asyncio.Event().wait()
            return iterate()

    class SocketContext:
        async def __aenter__(self):
            return Socket()

        async def __aexit__(self, *_args):
            return False

    monkeypatch.setattr(module, "PostgresCollectorLease", FakeLeaseManager)
    monkeypatch.setattr(module, "connect", lambda *_args, **_kwargs: SocketContext())
    collector = OrderBookStreamCollector(
        BlockingStore(), lambda: None, lambda _market: Provider(),
        jobs_json='[{"market":"SPOT","symbol":"BTCUSDT"}]',
        lease_database_url="postgresql://example/db",
    )

    async def scenario():
        task = asyncio.create_task(collector._run_job(collector._jobs()[0]))
        assert await asyncio.to_thread(insert_started.wait, 2)
        task.cancel()
        await asyncio.sleep(0.05)
        task.cancel()
        await asyncio.sleep(0.05)
        assert not task.done()
        assert released == []
        finish_insert.set()
        result = await asyncio.gather(task, return_exceptions=True)
        assert isinstance(result[0], asyncio.CancelledError)

    asyncio.run(scenario())
    assert released == [lease]
