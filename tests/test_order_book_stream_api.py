from fastapi.testclient import TestClient

from app import main
from app.main import app

client = TestClient(app)


def test_order_book_history_api_returns_local_samples(monkeypatch):
    class FakeStore:
        def recent(self, market, symbol, limit, start_time_ms, end_time_ms):
            return [{"market": market, "symbol": symbol.upper(), "update_id": 10}]

        def count(self):
            return 1

    monkeypatch.setattr(main, "order_book_history_store", FakeStore())
    response = client.get("/api/v1/history/order-book/USD_M/BTCUSDT")
    assert response.status_code == 200
    assert response.json()["returned_count"] == 1
    assert response.json()["coverage_warning"].startswith("Only locally captured")


def test_order_book_history_api_validates_time_range():
    response = client.get(
        "/api/v1/history/order-book/SPOT/BTCUSDT",
        params={"start_time_ms": 200, "end_time_ms": 100},
    )
    assert response.status_code == 422


def test_order_book_collector_status_reports_disabled(monkeypatch):
    monkeypatch.setattr(main.settings, "order_book_collector_enabled", False)
    class FakeStore:
        def count(self):
            return 7
    monkeypatch.setattr(main, "order_book_history_store", FakeStore())
    response = client.get("/api/v1/history/order-book/status")
    assert response.status_code == 200
    assert response.json()["status"] == "DISABLED"
    assert response.json()["stored_sample_count"] == 7
