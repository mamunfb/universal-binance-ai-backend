from fastapi.testclient import TestClient

from app import main
from app.main import app


client = TestClient(app)


class FakeSpotKlineProvider:
    def __init__(self, count):
        self.count = count

    async def klines(self, symbol, interval, limit):
        return [[index, "0", "0", "0", str(100 + index), "0"] for index in range(self.count)]


def test_spot_technical_api_marks_short_history_incomplete(monkeypatch):
    monkeypatch.setattr(main, "get_spot_provider", lambda: FakeSpotKlineProvider(60))
    response = client.get("/api/v1/analysis/spot/technical/BTCUSDT?limit=60")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "INCOMPLETE"
    assert "ema_100" in payload["missing_indicators"]
    assert "ema_200" in payload["missing_indicators"]


def test_spot_technical_api_reports_complete_required_indicators(monkeypatch):
    monkeypatch.setattr(main, "get_spot_provider", lambda: FakeSpotKlineProvider(250))
    response = client.get("/api/v1/analysis/spot/technical/BTCUSDT?limit=250")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "COMPLETED"
    assert payload["missing_indicators"] == []
    assert payload["indicators"]["ema_100"] is not None
    assert payload["indicators"]["sma_200"] is not None
