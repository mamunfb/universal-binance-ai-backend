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

def test_order_book_collector_status_distinguishes_idle_and_degraded(tmp_path):
    store = OrderBookHistoryStore(str(tmp_path / "book.sqlite3"))
    collector = OrderBookStreamCollector(store, lambda: None, lambda market: None)
    assert collector.status()["status"] == "IDLE"
    assert collector.status()["job_count"] == 0

    class ActiveTask:
        def done(self):
            return False

    collector.tasks = [ActiveTask(), ActiveTask()]
    collector.states = {
        "SPOT:BTCUSDT": {"connected": True, "last_error": None},
        "USD_M:BTCUSDT": {"connected": False, "last_error": "ConnectionError"},
    }
    status = collector.status()
    assert status["status"] == "DEGRADED"
    assert status["job_count"] == 2
    assert status["active_task_count"] == 2
    assert status["connected_job_count"] == 1
    assert status["disconnected_job_count"] == 1


@pytest.mark.parametrize("level", [
    ["inf", "1"], ["100", "nan"], ["100", "-1"], ["0", "1"], ["100"],
])
def test_order_book_delta_rejects_invalid_levels_without_mutating_side(tmp_path, level):
    collector = OrderBookStreamCollector(
        OrderBookHistoryStore(str(tmp_path / "book.sqlite3")),
        lambda: None, lambda market: None,
    )
    bids = {99.0: 2.0}
    with pytest.raises(ValueError):
        collector._apply({"b": [level], "a": []}, bids, {})
    assert bids == {99.0: 2.0}


@pytest.mark.parametrize("level", [
    ["inf", "1"], ["100", "nan"], ["100", "-1"], ["0", "1"], ["100"],
])
def test_order_book_snapshot_rejects_invalid_levels(level):
    with pytest.raises(ValueError):
        OrderBookStreamCollector._levels([level])


def test_order_book_delta_zero_quantity_removes_level(tmp_path):
    collector = OrderBookStreamCollector(
        OrderBookHistoryStore(str(tmp_path / "book.sqlite3")),
        lambda: None, lambda market: None,
    )
    bids = {100.0: 2.0}
    collector._apply({"b": [["100", "0"], ["99.5", "4"]], "a": []}, bids, {})
    assert bids == {99.5: 4.0}


def test_sample_skips_finite_levels_that_overflow_derived_metrics(tmp_path):
    collector = OrderBookStreamCollector(
        OrderBookHistoryStore(str(tmp_path / "book.sqlite3")),
        lambda: None, lambda market: None,
    )
    row = collector._sample(
        "SPOT", "BTCUSDT", {"E": 10, "T": 9}, 15,
        {1e200: 1e200}, {2e200: 1e200},
    )
    assert row is None


@pytest.mark.parametrize("event", [
    {"U": 10.5, "u": 12},
    {"U": 10, "u": "12.5"},
    {"U": True, "u": 12},
    {"U": 10, "u": 12, "pu": False},
])
def test_order_book_sequence_rejects_non_integer_ids(event):
    with pytest.raises(RuntimeError, match="DEPTH_INVALID_SEQUENCE"):
        OrderBookStreamCollector._validate_sequence("USD_M", event, 11, False)


@pytest.mark.parametrize("event", [
    {"E": 10.5, "T": 9},
    {"E": 10, "T": "9.5"},
    {"E": True, "T": 9},
])
def test_order_book_sample_rejects_non_integer_event_timestamps(tmp_path, event):
    collector = OrderBookStreamCollector(
        OrderBookHistoryStore(str(tmp_path / "book.sqlite3")),
        lambda: None, lambda market: None,
    )
    with pytest.raises(ValueError):
        collector._sample(
            "SPOT", "BTCUSDT", event, 15,
            {100.0: 2.0}, {101.0: 1.0},
        )
