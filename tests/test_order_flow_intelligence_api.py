from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app import main
from app.main import app

client = TestClient(app)


def test_order_flow_api_uses_local_trade_window(monkeypatch):
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

    class TradeStore:
        def recent(self, market, symbol, limit, start_time_ms=None, end_time_ms=None):
            assert market == "SPOT"
            assert symbol == "BTCUSDT"
            assert limit == 50000
            assert end_time_ms >= now_ms - 1000
            return [
                {"trade_time_ms": now_ms - 2000, "price": 100.0, "quantity": 2.0,
                 "notional": 200.0, "aggressor_side": "BUY"},
                {"trade_time_ms": now_ms - 1000, "price": 100.1, "quantity": 1.0,
                 "notional": 100.1, "aggressor_side": "SELL"},
            ]

    monkeypatch.setattr(main, "aggregate_trade_store", TradeStore())
    response = client.get("/api/v1/analysis/order-flow/SPOT/BTCUSDT")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "COMPLETED"
    assert payload["volume_profile"]["poc"]["volume_notional_proxy"] > 0
    assert payload["collector_coverage"]["query_limit"] == 50000


def test_order_flow_api_returns_insufficient_data(monkeypatch):
    class TradeStore:
        def recent(self, *args, **kwargs):
            return []

    monkeypatch.setattr(main, "aggregate_trade_store", TradeStore())
    response = client.get("/api/v1/analysis/order-flow/USD_M/BTCUSDT")
    assert response.status_code == 200
    assert response.json()["status"] == "INSUFFICIENT_DATA"


def test_order_flow_api_validates_parameters():
    response = client.get(
        "/api/v1/analysis/order-flow/SPOT/BTCUSDT",
        params={"lookback_minutes": 0},
    )
    assert response.status_code == 422
