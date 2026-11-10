from fastapi.testclient import TestClient

from app import main
from app.main import app

client = TestClient(app)


class FakeProvider:
    async def order_book(self, symbol, limit):
        return {
            "lastUpdateId": 99,
            "bids": [["100", "5"], ["99.9", "2"]],
            "asks": [["100.1", "1"], ["100.2", "2"]],
        }


def test_order_book_api_uses_spot_provider(monkeypatch):
    monkeypatch.setattr(main, "get_spot_provider", lambda: FakeProvider())
    response = client.get(
        "/api/v1/analysis/order-book/SPOT/BTCUSDT",
        params={"limit": 5, "wall_multiplier": 1},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "COMPLETED"
    assert response.json()["market"] == "SPOT"


def test_order_book_api_uses_futures_provider(monkeypatch):
    monkeypatch.setattr(main, "get_futures_provider", lambda market: FakeProvider())
    response = client.get("/api/v1/analysis/order-book/USD_M/BTCUSDT")
    assert response.status_code == 200
    assert response.json()["market"] == "USD_M"


def test_order_book_api_validates_market_and_depth(monkeypatch):
    response = client.get("/api/v1/analysis/order-book/INVALID/BTCUSDT")
    assert response.status_code == 422
    response = client.get("/api/v1/analysis/order-book/SPOT/BTCUSDT", params={"limit": 999})
    assert response.status_code == 422
