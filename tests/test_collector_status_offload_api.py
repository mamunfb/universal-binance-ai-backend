import asyncio
import threading
from types import SimpleNamespace

from app import main


def test_enabled_aggregate_trade_status_runs_count_off_event_loop(monkeypatch):
    observed_threads = []

    def fake_status():
        observed_threads.append(threading.get_ident())
        return {"stored_trade_count": 3}

    monkeypatch.setattr(main.settings, "aggregate_trade_collector_enabled", True)
    monkeypatch.setattr(main, "aggregate_trade_collector", SimpleNamespace(status=fake_status))

    async def invoke():
        event_loop_thread = threading.get_ident()
        response = await main.aggregate_trade_collector_status()
        return event_loop_thread, response

    event_loop_thread, response = asyncio.run(invoke())
    assert response["stored_trade_count"] == 3
    assert observed_threads and observed_threads[0] != event_loop_thread


def test_disabled_aggregate_trade_count_runs_off_event_loop(monkeypatch):
    observed_threads = []

    def fake_count():
        observed_threads.append(threading.get_ident())
        return 4

    monkeypatch.setattr(main.settings, "aggregate_trade_collector_enabled", False)
    monkeypatch.setattr(main.aggregate_trade_store, "count", fake_count)

    async def invoke():
        event_loop_thread = threading.get_ident()
        response = await main.aggregate_trade_collector_status()
        return event_loop_thread, response

    event_loop_thread, response = asyncio.run(invoke())
    assert response["status"] == "DISABLED"
    assert response["stored_trade_count"] == 4
    assert observed_threads and observed_threads[0] != event_loop_thread


def test_enabled_order_book_status_runs_count_off_event_loop(monkeypatch):
    observed_threads = []

    def fake_status():
        observed_threads.append(threading.get_ident())
        return {"stored_sample_count": 5}

    monkeypatch.setattr(main.settings, "order_book_collector_enabled", True)
    monkeypatch.setattr(main, "order_book_collector", SimpleNamespace(status=fake_status))

    async def invoke():
        event_loop_thread = threading.get_ident()
        response = await main.order_book_stream_status()
        return event_loop_thread, response

    event_loop_thread, response = asyncio.run(invoke())
    assert response["stored_sample_count"] == 5
    assert observed_threads and observed_threads[0] != event_loop_thread


def test_disabled_order_book_count_runs_off_event_loop(monkeypatch):
    observed_threads = []

    def fake_count():
        observed_threads.append(threading.get_ident())
        return 6

    monkeypatch.setattr(main.settings, "order_book_collector_enabled", False)
    monkeypatch.setattr(main.order_book_history_store, "count", fake_count)

    async def invoke():
        event_loop_thread = threading.get_ident()
        response = await main.order_book_stream_status()
        return event_loop_thread, response

    event_loop_thread, response = asyncio.run(invoke())
    assert response["status"] == "DISABLED"
    assert response["stored_sample_count"] == 6
    assert observed_threads and observed_threads[0] != event_loop_thread


def test_market_data_quality_offloads_database_backed_collector_status(monkeypatch):
    observed_threads = []

    def status(label):
        def read():
            observed_threads.append((label, threading.get_ident()))
            return {"status": "RUNNING", "label": label}
        return read

    class FakeQualityEngine:
        def __init__(self, *_args):
            pass

        def inspect(self, *_args):
            return {"status": "COMPLETED"}

    monkeypatch.setattr(main, "MarketDataQualityEngine", FakeQualityEngine)
    monkeypatch.setattr(main, "aggregate_trade_collector", SimpleNamespace(status=status("aggregate")))
    monkeypatch.setattr(main, "order_book_collector", SimpleNamespace(status=status("order_book")))
    monkeypatch.setattr(main, "historical_collector", None)
    monkeypatch.setattr(main, "derivatives_collector", None)
    monkeypatch.setattr(main.settings, "aggregate_trade_collector_enabled", True)
    monkeypatch.setattr(main.settings, "order_book_collector_enabled", True)
    monkeypatch.setattr(main.settings, "historical_collector_enabled", False)
    monkeypatch.setattr(main.settings, "derivatives_collector_enabled", False)

    async def invoke():
        event_loop_thread = threading.get_ident()
        report = await main.inspect_market_data_quality("SPOT", "BTCUSDT")
        return event_loop_thread, report

    event_loop_thread, report = asyncio.run(invoke())
    assert report["collectors"]["aggregate_trades"]["label"] == "aggregate"
    assert report["collectors"]["order_book"]["label"] == "order_book"
    assert {label for label, _thread in observed_threads} == {"aggregate", "order_book"}
    assert all(thread_id != event_loop_thread for _label, thread_id in observed_threads)
