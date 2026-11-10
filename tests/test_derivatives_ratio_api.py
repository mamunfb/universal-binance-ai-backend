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
