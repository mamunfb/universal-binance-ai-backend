from fastapi.testclient import TestClient

from app import main
from app.main import app

client = TestClient(app)


def test_liquidity_behavior_api_joins_recent_book_and_trade_samples(monkeypatch):
    class BookStore:
        def recent(self, market, symbol, limit, start_time_ms=None, end_time_ms=None):
            rows = [
                {"event_time_ms": 1000, "update_id": 1, "mid_price": 100.0,
                 "bids": [[99.9, 100]], "asks": [[100.1, 100]]},
                {"event_time_ms": 2000, "update_id": 2, "mid_price": 100.0,
                 "bids": [[99.9, 100]], "asks": [[100.1, 100]]},
            ]
            return rows[-limit:][::-1]

    class TradeStore:
        def recent(self, market, symbol, limit, start_time_ms=None, end_time_ms=None):
            return [{"trade_time_ms": 1500, "price": 100.1, "notional": 12000,
                     "aggressor_side": "BUY"}]

    monkeypatch.setattr(main, "order_book_history_store", BookStore())
    monkeypatch.setattr(main, "aggregate_trade_store", TradeStore())
    monkeypatch.setattr(main.settings, "order_book_collector_enabled", True)
    monkeypatch.setattr(main.settings, "aggregate_trade_collector_enabled", True)
    response = client.get("/api/v1/analysis/liquidity-behavior/SPOT/BTCUSDT")
    assert response.status_code == 200
    assert response.json()["status"] == "COMPLETED"
    assert response.json()["collector_coverage"]["aggregate_trade_samples_available"] == 1


def test_liquidity_behavior_api_returns_insufficient_data(monkeypatch):
    class BookStore:
        def recent(self, *args, **kwargs):
            return []
    monkeypatch.setattr(main, "order_book_history_store", BookStore())
    response = client.get("/api/v1/analysis/liquidity-behavior/SPOT/BTCUSDT")
    assert response.status_code == 200
    assert response.json()["status"] == "INSUFFICIENT_DATA"


def test_aggregate_trade_history_api_validates_time_range():
    response = client.get(
        "/api/v1/history/aggregate-trades/SPOT/BTCUSDT",
        params={"start_time_ms": 200, "end_time_ms": 100},
    )
    assert response.status_code == 422
