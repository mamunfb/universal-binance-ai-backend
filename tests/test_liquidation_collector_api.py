import threading

from fastapi.testclient import TestClient

from app import main
from app.main import app


client = TestClient(app)


def test_liquidation_status_runs_database_count_off_event_loop(monkeypatch):
    caller_thread = threading.get_ident()
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

    response = client.get("/api/v1/analysis/futures/liquidations/status")

    assert response.status_code == 200
    assert response.json()["storage_status"] == "AVAILABLE"
    assert observed_threads
    assert observed_threads[0] != caller_thread


def test_disabled_liquidation_status_also_runs_count_off_event_loop(monkeypatch):
    caller_thread = threading.get_ident()
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

    response = client.get("/api/v1/analysis/futures/liquidations/status")

    assert response.status_code == 200
    assert response.json()["status"] == "DISABLED"
    assert response.json()["collector_enabled"] is False
    assert response.json()["storage_status"] == "UNAVAILABLE"
    assert observed_threads
    assert observed_threads[0] != caller_thread
