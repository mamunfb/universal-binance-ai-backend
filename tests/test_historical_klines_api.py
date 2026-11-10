from fastapi.testclient import TestClient

from app import main
from app.main import app
from app.services.historical_klines import HistoricalKlineStore


client = TestClient(app)


class FakeSpot:
    async def klines(self, symbol, interval, limit):
        return [[1700000000000, "100", "105", "99", "101", "10",
                 1700000059999, "1000", 25, "4", "400", "0"]]


def test_collect_and_read_historical_spot_klines(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "get_spot_provider", lambda: FakeSpot())
    monkeypatch.setattr(
        main, "historical_kline_store",
        HistoricalKlineStore(str(tmp_path / "history.sqlite3")),
    )
    collected = client.post(
        "/api/v1/history/klines/SPOT/BTCUSDT/collect",
        params={"interval": "1m", "limit": 1},
    )
    assert collected.status_code == 200
    assert collected.json()["stored_count"] == 1
    history = client.get(
        "/api/v1/history/klines/SPOT/BTCUSDT",
        params={"interval": "1m"},
    )
    assert history.status_code == 200
    assert history.json()["candles"][0]["close"] == 101.0


def test_historical_kline_collection_sanitizes_upstream_failure(monkeypatch):
    class BrokenSpot:
        async def klines(self, symbol, interval, limit):
            raise RuntimeError("provider secret must not leak")

    monkeypatch.setattr(main, "get_spot_provider", lambda: BrokenSpot())
    response = client.post("/api/v1/history/klines/SPOT/BTCUSDT/collect")
    assert response.status_code == 502
    assert response.json()["detail"]["error"] == "HISTORICAL_KLINE_COLLECTION_UNAVAILABLE"
    assert "provider secret" not in response.text


def test_historical_kline_routes_validate_market_interval_and_bounds():
    bad_market = client.get("/api/v1/history/klines/OTHER/BTCUSDT")
    bad_interval = client.post(
        "/api/v1/history/klines/SPOT/BTCUSDT/collect",
        params={"interval": "2w"},
    )
    bad_range = client.get(
        "/api/v1/history/klines/SPOT/BTCUSDT",
        params={"start_time_ms": 100, "end_time_ms": 10},
    )
    assert bad_market.status_code == 422
    assert bad_interval.status_code == 422
    assert bad_range.status_code == 422
