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


@pytest.mark.parametrize("update_id", [True, 15.5, "15.5", float("inf")])
def test_order_book_sample_rejects_non_integer_update_ids(tmp_path, update_id):
    collector = OrderBookStreamCollector(
        OrderBookHistoryStore(str(tmp_path / "book.sqlite3")),
        lambda: None, lambda market: None,
    )
    with pytest.raises(ValueError):
        collector._sample(
            "SPOT", "BTCUSDT", {"E": 10, "T": 9}, update_id,
            {100.0: 2.0}, {101.0: 1.0},
        )


def test_order_book_strict_integer_accepts_integer_strings():
    assert OrderBookStreamCollector._strict_integer("123", "update ID") == 123


def _valid_store_row():
    return {
        "market": "USD_M", "symbol": "BTCUSDT", "event_time_ms": 1000,
        "transaction_time_ms": 1000, "update_id": 12,
        "sampled_at": "2026-01-01T00:00:00+00:00",
        "best_bid": 99.0, "best_ask": 101.0, "mid_price": 100.0,
        "spread_bps": 200.0, "bid_notional": 990.0, "ask_notional": 101.0,
        "depth_imbalance": 0.8, "bids": [[99.0, 10.0]], "asks": [[101.0, 1.0]],
    }


@pytest.mark.parametrize("field,value", [
    ("update_id", True),
    ("update_id", 12.5),
    ("event_time_ms", -1),
    ("best_bid", float("nan")),
    ("best_ask", float("inf")),
    ("mid_price", True),
    ("spread_bps", -1),
    ("bid_notional", float("inf")),
    ("depth_imbalance", 1.5),
    ("bids", [["99", "nan"]]),
    ("asks", [["101", -1]]),
    ("bids", [["99", 1], ["100", 1]]),
    ("market", "UNKNOWN"),
    ("symbol", ""),
])
def test_history_store_rejects_invalid_rows_before_insert(tmp_path, field, value):
    store = OrderBookHistoryStore(str(tmp_path / "book.sqlite3"))
    row = _valid_store_row()
    row[field] = value
    with pytest.raises(ValueError):
        store.insert(row)
    assert store.count() == 0


def test_history_store_rejects_non_object_row(tmp_path):
    store = OrderBookHistoryStore(str(tmp_path / "book.sqlite3"))
    with pytest.raises(ValueError):
        store.insert(None)
    assert store.count() == 0


@pytest.mark.parametrize("market,symbol,limit,start,end", [
    (None, "BTCUSDT", 10, None, None),
    ("UNKNOWN", "BTCUSDT", 10, None, None),
    ("SPOT", None, 10, None, None),
    ("SPOT", "BTCUSDT", True, None, None),
    ("SPOT", "BTCUSDT", 1.5, None, None),
    ("SPOT", "BTCUSDT", 0, None, None),
    ("SPOT", "BTCUSDT", 10001, None, None),
    ("SPOT", "BTCUSDT", 10, True, None),
    ("SPOT", "BTCUSDT", 10, 1.5, None),
    ("SPOT", "BTCUSDT", 10, None, -1),
    ("SPOT", "BTCUSDT", 10, 20, 10),
])
def test_history_store_recent_rejects_invalid_query_inputs(
    tmp_path, market, symbol, limit, start, end
):
    store = OrderBookHistoryStore(str(tmp_path / "book.sqlite3"))
    with pytest.raises(ValueError):
        store.recent(market, symbol, limit, start, end)


@pytest.mark.parametrize("market,symbol", [
    ("UNKNOWN", None),
    (True, None),
    (None, ""),
    (None, 123),
])
def test_history_store_count_rejects_invalid_filters(tmp_path, market, symbol):
    store = OrderBookHistoryStore(str(tmp_path / "book.sqlite3"))
    with pytest.raises(ValueError):
        store.count(market, symbol)


def test_history_store_recent_accepts_integer_string_query_bounds(tmp_path):
    store = OrderBookHistoryStore(str(tmp_path / "book.sqlite3"))
    assert store.recent("SPOT", "BTCUSDT", "10", "100", "200") == []


def test_history_store_query_market_filters_remain_case_insensitive(tmp_path):
    store = OrderBookHistoryStore(str(tmp_path / "book.sqlite3"))
    store.insert(_valid_store_row())
    assert store.recent("usd_m", "btcusdt", 10)[0]["symbol"] == "BTCUSDT"
    assert store.count("usd_m", "btcusdt") == 1


@pytest.mark.parametrize("field,value", [
    ("update_id", 2**63),
    ("event_time_ms", 2**63),
    ("transaction_time_ms", 2**63),
])
def test_history_store_rejects_integer_fields_outside_storage_range(tmp_path, field, value):
    store = OrderBookHistoryStore(str(tmp_path / "book.sqlite3"))
    row = _valid_store_row()
    row[field] = value
    with pytest.raises(ValueError):
        store.insert(row)
    assert store.count() == 0


@pytest.mark.parametrize("start,end", [
    (2**63, None),
    (None, 2**63),
])
def test_history_store_recent_rejects_time_bounds_outside_storage_range(tmp_path, start, end):
    store = OrderBookHistoryStore(str(tmp_path / "book.sqlite3"))
    with pytest.raises(ValueError):
        store.recent("SPOT", "BTCUSDT", 10, start, end)


def test_history_store_count_none_none_returns_unfiltered_total(tmp_path):
    store = OrderBookHistoryStore(str(tmp_path / "book.sqlite3"))
    store.insert(_valid_store_row())
    assert store.count(None, None) == 1



def test_postgres_history_store_insert_recent_and_count(monkeypatch, tmp_path):
    from app.services import order_book_stream as order_book_stream_module

    class FakePostgresConnection:
        def __init__(self):
            self.statements = []
            self.inserted = None

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def execute(self, query, params=()):
            self.statements.append((query, params))
            if query.lstrip().startswith("INSERT INTO public.order_book_samples"):
                self.inserted = params
            return self

        def fetchone(self):
            return {"count": 1}

        def fetchall(self):
            return [{
                "market": "USD_M", "symbol": "BTCUSDT", "event_time_ms": 1000,
                "transaction_time_ms": 1000, "update_id": 12,
                "sampled_at": "2026-01-01T00:00:00+00:00",
                "best_bid": 99.0, "best_ask": 101.0, "mid_price": 100.0,
                "spread_bps": 200.0, "bid_notional": 990.0, "ask_notional": 101.0,
                "depth_imbalance": 0.8, "bids": [[99.0, 10.0]], "asks": [[101.0, 1.0]],
            }]

    fake_db = FakePostgresConnection()
    monkeypatch.setattr(order_book_stream_module.psycopg, "connect", lambda *args, **kwargs: fake_db)
    store = OrderBookHistoryStore(str(tmp_path / "unused.sqlite3"), database_url="postgresql://db.example/test")
    row = _valid_store_row()
    store.insert(row)

    insert_sql, insert_params = fake_db.statements[-1]
    assert "ON CONFLICT(market, symbol, update_id) DO NOTHING" in insert_sql
    assert insert_params[0:5] == ("USD_M", "BTCUSDT", 1000, 1000, 12)
    assert json.loads(insert_params[-2]) == [[99.0, 10.0]]
    assert json.loads(insert_params[-1]) == [[101.0, 1.0]]

    recent = store.recent("usd_m", "btcusdt", 10, 500, 1500)
    recent_sql, recent_params = fake_db.statements[-1]
    assert "event_time_ms >= %s" in recent_sql
    assert "event_time_ms <= %s" in recent_sql
    assert recent_params == ["USD_M", "BTCUSDT", 500, 1500, 10]
    assert recent[0]["bids"] == [[99.0, 10.0]]
    assert recent[0]["asks"] == [[101.0, 1.0]]

    assert store.count("usd_m", "btcusdt") == 1
    count_sql, count_params = fake_db.statements[-1]
    assert "FROM public.order_book_samples" in count_sql
    assert count_params == ["USD_M", "BTCUSDT"]
