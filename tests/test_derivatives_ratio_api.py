from fastapi.testclient import TestClient

from app import main
from app.main import app

client = TestClient(app)


def test_collect_global_ratio_and_read_history(monkeypatch):
    class FakeProvider:
        async def global_long_short_ratio(self, symbol, period, limit):
            return [{
                "symbol": symbol, "timestamp": 1700000000000,
                "longShortRatio": "1.2", "longAccount": "0.55", "shortAccount": "0.45",
            }]

    monkeypatch.setattr(main, "get_futures_provider", lambda market: FakeProvider())
    response = client.post(
        "/api/v1/history/derivatives-ratios/USD_M/GLOBAL_LONG_SHORT/BTCUSDT/collect",
        params={"period": "1h", "limit": 10},
    )
    assert response.status_code == 200
    assert response.json()["stored_count"] == 1
    history = client.get(
        "/api/v1/history/derivatives-ratios/USD_M/GLOBAL_LONG_SHORT/BTCUSDT",
        params={"period": "1h"},
    )
    assert history.status_code == 200
    assert history.json()["records"][0]["long_short_ratio"] == 1.2


def test_collect_taker_ratio(monkeypatch):
    class FakeProvider:
        async def taker_long_short_ratio(self, symbol, period, limit):
            return [{
                "symbol": symbol, "timestamp": 1700000000000,
                "buySellRatio": "1.1", "buyVol": "110", "sellVol": "100",
            }]

    monkeypatch.setattr(main, "get_futures_provider", lambda market: FakeProvider())
    response = client.post(
        "/api/v1/history/derivatives-ratios/USD_M/TAKER_BUY_SELL/BTCUSDT/collect"
    )
    assert response.status_code == 200
    assert response.json()["ratio_type"] == "TAKER_BUY_SELL"


def test_ratio_collection_rejects_unsupported_market_period_and_ratio():
    base = "/api/v1/history/derivatives-ratios/USD_M"
    assert client.post(f"{base}/GLOBAL_LONG_SHORT/BTCUSDT/collect", params={"period": "2w"}).status_code == 422
    assert client.post(f"{base}/UNKNOWN/BTCUSDT/collect").status_code == 422
    assert client.get(f"{base}/UNKNOWN/BTCUSDT").status_code == 422


def test_ratio_collection_reports_empty_provider_response(monkeypatch):
    class FakeProvider:
        async def global_long_short_ratio(self, *_args):
            return []

    monkeypatch.setattr(main, "get_futures_provider", lambda market: FakeProvider())
    response = client.post(
        "/api/v1/history/derivatives-ratios/USD_M/GLOBAL_LONG_SHORT/BTCUSDT/collect"
    )
    assert response.status_code == 200
    assert response.json()["status"] == "NO_NEW_DATA"


def test_manual_ratio_collection_uses_per_series_lease_and_fences_store(monkeypatch):
    from types import SimpleNamespace

    captured = {"released": [], "saved": None}
    lease = SimpleNamespace(fencing_token=31)

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
        async def global_long_short_ratio(self, symbol, period, limit):
            return [{
                "symbol": symbol, "timestamp": 1700000000000,
                "longShortRatio": "1.2", "longAccount": "0.55", "shortAccount": "0.45",
            }]

    class FakeStore:
        def save(self, ratio_type, symbol, period, rows, source, lease=None):
            captured["saved"] = (ratio_type, symbol, period, source, lease)
            return {"status": "COMPLETED", "stored_count": len(rows)}

    monkeypatch.setattr(main.settings, "database_url", "postgresql://example/test")
    monkeypatch.setattr(main.settings, "derivatives_collector_lease_ttl_seconds", 30)
    monkeypatch.setattr(main, "PostgresCollectorLease", FakeLeaseManager)
    monkeypatch.setattr(main, "get_futures_provider", lambda _market: FakeProvider())
    monkeypatch.setattr(main, "derivatives_ratio_store", FakeStore())

    response = client.post(
        "/api/v1/history/derivatives-ratios/USD_M/GLOBAL_LONG_SHORT/BTCUSDT/collect"
    )

    assert response.status_code == 200
    assert captured["manager"] == (
        "postgresql://example/test", "derivatives-ratio:GLOBAL_LONG_SHORT:BTCUSDT:1h", 30
    )
    assert captured["saved"][0:3] == ("GLOBAL_LONG_SHORT", "BTCUSDT", "1h")
    assert captured["saved"][3] == "Binance USD-M Futures public REST API (manual collection)"
    assert captured["saved"][4] is lease
    assert captured["released"] == [lease]


def test_manual_ratio_collection_returns_conflict_without_provider_call(monkeypatch):
    captured = {"provider_called": False}

    class FakeLeaseManager:
        def __init__(self, *_args, **_kwargs):
            pass

        def acquire(self):
            return None

    def provider_factory(_market):
        captured["provider_called"] = True
        raise AssertionError("Provider must not be called while the series lease is held")

    monkeypatch.setattr(main.settings, "database_url", "postgresql://example/test")
    monkeypatch.setattr(main, "PostgresCollectorLease", FakeLeaseManager)
    monkeypatch.setattr(main, "get_futures_provider", provider_factory)

    response = client.post(
        "/api/v1/history/derivatives-ratios/USD_M/GLOBAL_LONG_SHORT/BTCUSDT/collect"
    )

    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "DERIVATIVES_RATIO_COLLECTION_LEASE_HELD"
    assert captured["provider_called"] is False
