from fastapi.testclient import TestClient

from app import main
from app.main import app

client = TestClient(app)


def test_aggregate_trade_history_api_returns_local_rows(monkeypatch):
    class FakeStore:
        def recent(self, market, symbol, limit, start_time_ms, end_time_ms):
            return [{"market": market, "symbol": symbol.upper(), "trade_id": 4}]
        def count(self):
            return 1

    monkeypatch.setattr(main, "aggregate_trade_store", FakeStore())
    response = client.get("/api/v1/history/aggregate-trades/USD_M/BTCUSDT")
    assert response.status_code == 200
    assert response.json()["returned_count"] == 1
    assert response.json()["trades"][0]["trade_id"] == 4


def test_aggregate_trade_status_reports_disabled(monkeypatch):
    class FakeStore:
        def count(self):
            return 2
    monkeypatch.setattr(main, "aggregate_trade_store", FakeStore())
    monkeypatch.setattr(main.settings, "aggregate_trade_collector_enabled", False)
    response = client.get("/api/v1/history/aggregate-trades/status")
    assert response.status_code == 200
    assert response.json()["status"] == "DISABLED"
    assert response.json()["stored_trade_count"] == 2
