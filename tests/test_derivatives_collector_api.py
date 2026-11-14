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


def test_manual_funding_collection_uses_shared_derivatives_lease(monkeypatch):
    from types import SimpleNamespace

    captured = {"released": [], "saved": None}
    lease = SimpleNamespace(fencing_token=21)

    class FakeLeaseManager:
        def __init__(self, database_url, lease_name, ttl_seconds):
            captured["manager"] = (database_url, lease_name, ttl_seconds)

        def acquire(self):
            return lease

        def renew(self, current):
            assert current is lease
            return lease

        def release(self, current):
            captured["released"].append(current)
            return True

    class FakeProvider:
        async def funding_rate(self, symbol, **kwargs):
            captured["provider"] = (symbol, kwargs)
            return [{"symbol": "BTCUSDT", "fundingTime": 1000, "fundingRate": "0.0001", "markPrice": "50000"}]

    class FakeStore:
        def save(self, market, symbol, rows, source, lease=None):
            captured["saved"] = (market, symbol, rows, source, lease)
            return {"status": "COMPLETED", "stored_count": 1}

    monkeypatch.setattr(main.settings, "database_url", "postgresql://example/test")
    monkeypatch.setattr(main.settings, "derivatives_collector_lease_ttl_seconds", 45)
    monkeypatch.setattr(main, "PostgresCollectorLease", FakeLeaseManager)
    monkeypatch.setattr(main, "get_futures_provider", lambda market: FakeProvider())
    monkeypatch.setattr(main, "funding_rate_store", FakeStore())

    response = client.post("/api/v1/history/funding-rates/USD_M/BTCUSDT/collect")

    assert response.status_code == 200
    assert response.json()["status"] == "COMPLETED"
    assert captured["manager"] == (
        "postgresql://example/test", "derivatives-history-collector", 45
    )
    assert captured["saved"][0:2] == ("USD_M", "BTCUSDT")
    assert captured["saved"][3] == "Binance USD-M public REST API (manual collection)"
    assert captured["saved"][4] is lease
    assert captured["released"] == [lease]


def test_manual_open_interest_collection_returns_conflict_without_provider_call(monkeypatch):
    captured = {"provider_called": False, "released": []}

    class FakeLeaseManager:
        def __init__(self, *_args, **_kwargs):
            pass

        def acquire(self):
            return None

        def release(self, lease):
            captured["released"].append(lease)
            return True

    def provider_factory(_market):
        captured["provider_called"] = True
        raise AssertionError("Provider must not be called while scheduled lease is held")

    monkeypatch.setattr(main.settings, "database_url", "postgresql://example/test")
    monkeypatch.setattr(main, "PostgresCollectorLease", FakeLeaseManager)
    monkeypatch.setattr(main, "get_futures_provider", provider_factory)

    response = client.post("/api/v1/history/open-interest/USD_M/BTCUSDT/collect")

    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "DERIVATIVES_COLLECTION_LEASE_HELD"
    assert captured["provider_called"] is False
    assert captured["released"] == []
