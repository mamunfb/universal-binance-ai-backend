from fastapi.testclient import TestClient

from app import main
from app.main import app
from app.services.liquidation_collector import LiquidationStore

client = TestClient(app)


def _event(ts, side, price, qty):
    return {
        "event_time_ms": ts, "trade_time_ms": ts, "symbol": "BTCUSDT",
        "pair_symbol": "BTCUSDT", "market_type": 1, "side": side,
        "order_type": "LIMIT", "status": "FILLED", "average_price": price,
        "original_quantity": qty, "last_filled_quantity": qty,
        "cumulative_filled_quantity": qty,
        "approx_cumulative_notional": price * qty, "raw_json": "{}",
    }


def test_liquidation_cluster_api_uses_local_store(monkeypatch, tmp_path):
    store = LiquidationStore(str(tmp_path / "liquidations.sqlite3"))
    store.insert(_event(1000, "SELL", 60000, 0.1))
    store.insert(_event(2000, "SELL", 60010, 0.2))
    monkeypatch.setattr(main, "liquidation_store", store)
    response = client.get(
        "/api/v1/analysis/futures/liquidation-clusters/BTCUSDT",
        params={"bucket_bps": 25, "limit": 100},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "COMPLETED"
    assert payload["coverage"]["events_usable"] == 2
    assert payload["clusters"][0]["sell_side_events"] == 2


def test_liquidation_cluster_api_validates_parameters():
    base = "/api/v1/analysis/futures/liquidation-clusters/BTCUSDT"
    assert client.get(base, params={"bucket_bps": 0}).status_code == 422
    assert client.get(base, params={"limit": 0}).status_code == 422
    assert client.get(base, params={
        "start_time_ms": 200, "end_time_ms": 100
    }).status_code == 422
