from fastapi.testclient import TestClient

from app import main
from app.main import app
from app.services.open_interest import OpenInterestStore


client = TestClient(app)


class FakeFutures:
    async def open_interest_history(
        self, symbol, period="1h", limit=30, start_time_ms=None, end_time_ms=None
    ):
        return [{
            "symbol": symbol, "timestamp": 1700000000000,
            "sumOpenInterest": "123.45", "sumOpenInterestValue": "4567890.12",
            "CMCCirculatingSupply": "19000000",
        }]


def test_collect_and_read_open_interest_history(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "get_futures_provider", lambda _market: FakeFutures())
    monkeypatch.setattr(main, "open_interest_store",
                        OpenInterestStore(str(tmp_path / "oi.sqlite3")))
    collected = client.post(
        "/api/v1/history/open-interest/USD_M/BTCUSDT/collect",
        params={"period": "1h", "limit": 20},
    )
    assert collected.status_code == 200
    assert collected.json()["stored_count"] == 1
    history = client.get(
        "/api/v1/history/open-interest/USD_M/BTCUSDT",
        params={"period": "1h"},
    )
    assert history.status_code == 200
    assert history.json()["records"][0]["sum_open_interest_value"] == 4567890.12


def test_open_interest_collection_validates_range_and_sanitizes_failure(monkeypatch):
    bad_range = client.post(
        "/api/v1/history/open-interest/USD_M/BTCUSDT/collect",
        params={"start_time_ms": 100, "end_time_ms": 10},
    )
    assert bad_range.status_code == 422

    class Broken:
        async def open_interest_history(self, *args, **kwargs):
            raise RuntimeError("private upstream response")

    monkeypatch.setattr(main, "get_futures_provider", lambda _market: Broken())
    response = client.post("/api/v1/history/open-interest/USD_M/BTCUSDT/collect")
    assert response.status_code == 502
    assert "OPEN_INTEREST_COLLECTION_UNAVAILABLE" in response.text
    assert "private upstream response" not in response.text


def test_open_interest_collection_returns_no_new_data(monkeypatch):
    class Empty:
        async def open_interest_history(self, *args, **kwargs):
            return []

    monkeypatch.setattr(main, "get_futures_provider", lambda _market: Empty())
    response = client.post("/api/v1/history/open-interest/USD_M/BTCUSDT/collect")
    assert response.status_code == 200
    assert response.json()["status"] == "NO_NEW_DATA"
