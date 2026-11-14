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


def test_manual_kline_collection_uses_scheduled_lease_and_releases(monkeypatch):
    from types import SimpleNamespace

    captured = {"saved": None, "released": []}
    lease = SimpleNamespace(fencing_token=9)

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
        async def klines(self, symbol, interval, limit):
            captured["provider"] = (symbol, interval, limit)
            return [[1, "100", "105", "99", "101", "10", 60000, "1000", 2, "4", "400", "0"]]

    class FakeStore:
        def save_klines(self, market, symbol, interval, rows, source, lease=None):
            captured["saved"] = (market, symbol, interval, rows, source, lease)
            return {"status": "COMPLETED", "stored_count": 1}

    monkeypatch.setattr(main.settings, "database_url", "postgresql://example/test")
    monkeypatch.setattr(main.settings, "historical_kline_database_url", "")
    monkeypatch.setattr(main.settings, "historical_collector_lease_ttl_seconds", 30)
    monkeypatch.setattr(main, "PostgresCollectorLease", FakeLeaseManager)
    monkeypatch.setattr(main, "get_spot_provider", lambda: FakeProvider())
    monkeypatch.setattr(main, "historical_kline_store", FakeStore())

    response = client.post("/api/v1/history/klines/SPOT/BTCUSDT/collect?interval=1m&limit=1")

    assert response.status_code == 200
    assert response.json()["status"] == "COMPLETED"
    assert captured["manager"] == (
        "postgresql://example/test", "historical-kline-collector", 30
    )
    assert captured["provider"] == ("BTCUSDT", "1m", 1)
    assert captured["saved"][0:3] == ("SPOT", "BTCUSDT", "1m")
    assert captured["saved"][4] == "Binance public REST API (manual collection)"
    assert captured["saved"][5] is lease
    assert captured["released"] == [lease]


def test_manual_kline_collection_returns_conflict_when_scheduled_lease_is_held(monkeypatch):
    captured = {"provider_called": False, "released": []}

    class FakeLeaseManager:
        def __init__(self, *_args, **_kwargs):
            pass

        def acquire(self):
            return None

        def release(self, lease):
            captured["released"].append(lease)
            return True

    def provider_factory():
        captured["provider_called"] = True
        raise AssertionError("Provider must not be called without the lease")

    monkeypatch.setattr(main.settings, "database_url", "postgresql://example/test")
    monkeypatch.setattr(main.settings, "historical_kline_database_url", "")
    monkeypatch.setattr(main, "PostgresCollectorLease", FakeLeaseManager)
    monkeypatch.setattr(main, "get_spot_provider", provider_factory)

    response = client.post("/api/v1/history/klines/SPOT/BTCUSDT/collect")

    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "HISTORICAL_COLLECTION_LEASE_HELD"
    assert captured["provider_called"] is False
    assert captured["released"] == []


def test_manual_kline_collection_releases_lease_when_provider_fails(monkeypatch):
    from types import SimpleNamespace

    lease = SimpleNamespace(fencing_token=11)
    captured = {"released": []}

    class FakeLeaseManager:
        def __init__(self, *_args, **_kwargs):
            pass

        def acquire(self):
            return lease

        def release(self, current):
            captured["released"].append(current)
            return True

    class BrokenProvider:
        async def klines(self, *_args, **_kwargs):
            raise RuntimeError("upstream unavailable")

    monkeypatch.setattr(main.settings, "database_url", "postgresql://example/test")
    monkeypatch.setattr(main.settings, "historical_kline_database_url", "")
    monkeypatch.setattr(main, "PostgresCollectorLease", FakeLeaseManager)
    monkeypatch.setattr(main, "get_spot_provider", lambda: BrokenProvider())

    response = client.post("/api/v1/history/klines/SPOT/BTCUSDT/collect")

    assert response.status_code == 502
    assert captured["released"] == [lease]
