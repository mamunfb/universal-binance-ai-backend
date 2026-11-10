from fastapi.testclient import TestClient

from app import main
from app.main import app


client = TestClient(app)


def test_derivatives_collector_status_is_disabled_by_default(monkeypatch):
    monkeypatch.setattr(main.settings, "derivatives_collector_enabled", False)
    response = client.get("/api/v1/history/derivatives-collector/status")
    assert response.status_code == 200
    assert response.json() == {"status": "DISABLED", "enabled": False, "jobs": []}


def test_derivatives_collector_status_reports_configured_instance(monkeypatch):
    class FakeCollector:
        def status(self):
            return {"status": "RUNNING", "enabled": True, "job_count": 1}

    monkeypatch.setattr(main.settings, "derivatives_collector_enabled", True)
    monkeypatch.setattr(main, "derivatives_collector", FakeCollector())
    response = client.get("/api/v1/history/derivatives-collector/status")
    assert response.status_code == 200
    assert response.json()["status"] == "RUNNING"
