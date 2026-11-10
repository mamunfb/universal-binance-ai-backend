from fastapi.testclient import TestClient

from app import main
from app.main import app
from app.services.funding_rates import FundingRateStore


client = TestClient(app)


class FakeFutures:
    async def funding_rate(self, symbol, limit=1000, start_time_ms=None, end_time_ms=None):
        return [{"symbol": symbol, "fundingTime": 1700000000000,
                 "fundingRate": "0.0001", "markPrice": "37000"}]


def test_collect_and_read_funding_rate_history(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "get_futures_provider", lambda _market: FakeFutures())
    monkeypatch.setattr(main, "funding_rate_store",
                        FundingRateStore(str(tmp_path / "funding.sqlite3")))
    collected = client.post("/api/v1/history/funding-rates/USD_M/BTCUSDT/collect")
    assert collected.status_code == 200
    assert collected.json()["stored_count"] == 1
    history = client.get("/api/v1/history/funding-rates/USD_M/BTCUSDT")
    assert history.status_code == 200
    assert history.json()["events"][0]["funding_rate"] == 0.0001


def test_funding_collection_validates_bounds_and_sanitizes_failure(monkeypatch):
    bad_range = client.post(
        "/api/v1/history/funding-rates/USD_M/BTCUSDT/collect",
        params={"start_time_ms": 100, "end_time_ms": 10},
    )
    assert bad_range.status_code == 422

    class Broken:
        async def funding_rate(self, *args, **kwargs):
            raise RuntimeError("sensitive upstream text")

    monkeypatch.setattr(main, "get_futures_provider", lambda _market: Broken())
    response = client.post("/api/v1/history/funding-rates/USD_M/BTCUSDT/collect")
    assert response.status_code == 502
    assert "FUNDING_RATE_COLLECTION_UNAVAILABLE" in response.text
    assert "sensitive upstream text" not in response.text
