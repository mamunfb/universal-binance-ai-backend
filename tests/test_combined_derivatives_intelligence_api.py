from fastapi.testclient import TestClient

from app import main
from app.main import app

client = TestClient(app)


def test_combined_derivatives_api_uses_stores(monkeypatch):
    calls = []

    class FakeEngine:
        def __init__(self, oi, funding, ratios):
            assert oi is main.open_interest_store
            assert funding is main.funding_rate_store
            assert ratios is main.derivatives_ratio_store

        def analyze(self, symbol, period, limit):
            calls.append((symbol, period, limit))
            return {"status": "COMPLETED", "symbol": symbol}

    monkeypatch.setattr(main, "CombinedDerivativesIntelligence", FakeEngine)
    response = client.get(
        "/api/v1/analysis/derivatives/combined/BTCUSDT",
        params={"period": "4h", "limit": 50},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "COMPLETED"
    assert calls == [("BTCUSDT", "4h", 50)]


def test_combined_derivatives_api_validates_period_and_limit():
    base = "/api/v1/analysis/derivatives/combined/BTCUSDT"
    assert client.get(base, params={"period": "2w"}).status_code == 422
    assert client.get(base, params={"limit": 1}).status_code == 422
