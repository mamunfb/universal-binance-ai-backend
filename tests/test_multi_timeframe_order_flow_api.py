from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app import main
from app.main import app

client = TestClient(app)


def test_multi_timeframe_order_flow_api(monkeypatch):
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

    class TradeStore:
        def recent(self, market, symbol, limit, start_time_ms=None, end_time_ms=None):
            assert market == "USD_M"
            assert symbol == "BTCUSDT"
            assert limit == 50000
            return [
                {"trade_time_ms": now_ms - 120_000, "price": 100.0, "quantity": 2.0,
                 "notional": 200.0, "aggressor_side": "BUY"},
                {"trade_time_ms": now_ms - 60_000, "price": 100.1, "quantity": 1.0,
                 "notional": 100.1, "aggressor_side": "SELL"},
            ]

    monkeypatch.setattr(main, "aggregate_trade_store", TradeStore())
    response = client.get(
        "/api/v1/analysis/order-flow/multi-timeframe/USD_M/BTCUSDT",
        params={"periods": "5m,15m"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["timeframe_count"] == 2
    assert payload["completed_timeframe_count"] == 2
    assert payload["collector_coverage"]["query_limit"] == 50000


def test_multi_timeframe_order_flow_api_rejects_unknown_period():
    response = client.get(
        "/api/v1/analysis/order-flow/multi-timeframe/SPOT/BTCUSDT",
        params={"periods": "5m,2d"},
    )
    assert response.status_code == 422
