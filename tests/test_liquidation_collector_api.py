import asyncio
import threading

from app import main


def test_liquidation_status_runs_database_count_off_event_loop(monkeypatch):
    observed_threads = []

    def fake_status():
        observed_threads.append(threading.get_ident())
        return {
            "collector_enabled": True,
            "stored_event_count": 0,
            "storage_status": "AVAILABLE",
            "storage_error": None,
        }

    monkeypatch.setattr(main.settings, "liquidation_collector_enabled", True)
    monkeypatch.setattr(main.liquidation_collector, "status", fake_status)

    async def invoke():
        event_loop_thread = threading.get_ident()
        response = await main.liquidation_collector_status()
        return event_loop_thread, response

    event_loop_thread, response = asyncio.run(invoke())

    assert response["storage_status"] == "AVAILABLE"
    assert observed_threads
    assert observed_threads[0] != event_loop_thread


def test_disabled_liquidation_status_also_runs_count_off_event_loop(monkeypatch):
    observed_threads = []

    def fake_status():
        observed_threads.append(threading.get_ident())
        return {
            "collector_enabled": True,
            "stored_event_count": None,
            "storage_status": "UNAVAILABLE",
            "storage_error": "OperationalError",
        }

    monkeypatch.setattr(main.settings, "liquidation_collector_enabled", False)
    monkeypatch.setattr(main.liquidation_collector, "status", fake_status)

    async def invoke():
        event_loop_thread = threading.get_ident()
        response = await main.liquidation_collector_status()
        return event_loop_thread, response

    event_loop_thread, response = asyncio.run(invoke())

    assert response["status"] == "DISABLED"
    assert response["collector_enabled"] is False
    assert response["storage_status"] == "UNAVAILABLE"
    assert observed_threads
    assert observed_threads[0] != event_loop_thread
