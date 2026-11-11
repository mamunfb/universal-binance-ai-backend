import asyncio
import json

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

@pytest.mark.parametrize("market", ["USD_M", "COIN_M"])
def test_futures_depth_first_event_accepts_snapshot_overlap(tmp_path, market):
    collector = OrderBookStreamCollector(
        OrderBookHistoryStore(str(tmp_path / f"{market}.sqlite3")),
        lambda: None, lambda _market: None,
    )
    collector._validate_sequence(
        market, {"U": 99, "u": 101, "pu": 98}, last_id=100, first_event=True,
    )


@pytest.mark.parametrize("market", ["USD_M", "COIN_M"])
def test_futures_depth_first_event_accepts_direct_pu_continuation(tmp_path, market):
    collector = OrderBookStreamCollector(
        OrderBookHistoryStore(str(tmp_path / f"{market}.sqlite3")),
        lambda: None, lambda _market: None,
    )
    collector._validate_sequence(
        market, {"U": 101, "u": 105, "pu": 100}, last_id=100, first_event=True,
    )


@pytest.mark.parametrize("market", ["USD_M", "COIN_M"])
def test_futures_depth_first_event_rejects_unbridged_update_gap(tmp_path, market):
    collector = OrderBookStreamCollector(
        OrderBookHistoryStore(str(tmp_path / f"{market}.sqlite3")),
        lambda: None, lambda _market: None,
    )
    with pytest.raises(RuntimeError, match="DEPTH_INITIAL_SEQUENCE_GAP"):
        collector._validate_sequence(
            market, {"U": 101, "u": 105, "pu": 99}, last_id=100, first_event=True,
        )


def test_spot_depth_first_event_keeps_spot_update_id_rule(tmp_path):
    collector = OrderBookStreamCollector(
        OrderBookHistoryStore(str(tmp_path / "spot.sqlite3")),
        lambda: None, lambda _market: None,
    )
    collector._validate_sequence(
        "SPOT", {"U": 99, "u": 101}, last_id=100, first_event=True,
    )
    with pytest.raises(RuntimeError, match="DEPTH_INITIAL_SEQUENCE_GAP"):
        collector._validate_sequence(
            "SPOT", {"U": 102, "u": 105}, last_id=100, first_event=True,
        )


@pytest.mark.parametrize("event", [
    {"U": 100.5, "u": 101, "pu": 99},
    {"U": 100, "u": True, "pu": 99},
    {"U": 100, "u": 101, "pu": 99.5},
])
def test_futures_depth_sequence_rejects_non_integer_update_ids(tmp_path, event):
    collector = OrderBookStreamCollector(
        OrderBookHistoryStore(str(tmp_path / "malformed.sqlite3")),
        lambda: None, lambda _market: None,
    )
    with pytest.raises(RuntimeError, match="DEPTH_INVALID_SEQUENCE_ID"):
        collector._validate_sequence("USD_M", event, last_id=100, first_event=True)



class _EmptyAsyncSocket:
    def __aiter__(self):
        async def _empty():
            if False:
                yield None
        return _empty()


@pytest.mark.asyncio
async def test_reader_signals_stream_end_when_queue_is_full(tmp_path):
    collector = OrderBookStreamCollector(
        OrderBookHistoryStore(str(tmp_path / "reader.sqlite3")),
        lambda: None, lambda _market: None,
    )
    queue = asyncio.Queue(maxsize=1)
    queue.put_nowait({"u": 10})

    await collector._reader(_EmptyAsyncSocket(), queue)

    assert queue.get_nowait() is None


@pytest.mark.asyncio
async def test_reader_cancellation_signals_shutdown_when_queue_is_full(tmp_path):
    collector = OrderBookStreamCollector(
        OrderBookHistoryStore(str(tmp_path / "reader-cancel.sqlite3")),
        lambda: None, lambda _market: None,
    )
    queue = asyncio.Queue(maxsize=1)
    queue.put_nowait({"u": 10})
    blocked = asyncio.Event()

    class _BlockingAsyncSocket:
        def __aiter__(self):
            async def _wait():
                await blocked.wait()
                yield "{}"
            return _wait()

    reader = asyncio.create_task(collector._reader(_BlockingAsyncSocket(), queue))
    await asyncio.sleep(0)
    reader.cancel()
    await asyncio.gather(reader, return_exceptions=True)

    assert queue.get_nowait() is None
