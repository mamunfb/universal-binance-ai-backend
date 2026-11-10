from fastapi.testclient import TestClient

from app import main
from app.main import app

client = TestClient(app)


def test_historical_collector_status_is_disabled_by_default(monkeypatch):
    monkeypatch.setattr(main.settings, "historical_collector_enabled", False)
    response = client.get("/api/v1/history/collector/status")
    assert response.status_code == 200
    assert response.json()["status"] == "DISABLED"
    assert response.json()["enabled"] is False


def test_historical_collector_status_reports_starting_when_enabled_without_lifespan(monkeypatch):
    monkeypatch.setattr(main.settings, "historical_collector_enabled", True)
    monkeypatch.setattr(main, "historical_collector", None)
    response = client.get("/api/v1/history/collector/status")
    assert response.status_code == 200
    assert response.json()["status"] == "STARTING"
