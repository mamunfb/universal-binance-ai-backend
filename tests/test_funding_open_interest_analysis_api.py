from fastapi.testclient import TestClient

from app import main
from app.main import app

client = TestClient(app)


def test_combined_derivatives_analysis_endpoint_uses_local_stores(monkeypatch):
    class Analysis:
        def __init__(self, funding, oi, klines):
            assert funding is main.funding_rate_store
            assert oi is main.open_interest_store
            assert klines is main.historical_kline_store

        def analyze(self, symbol, period, price_interval, limit):
            return {"status": "COMPLETED", "symbol": symbol.upper(),
                    "period": period, "price_interval": price_interval, "limit": limit}

    monkeypatch.setattr(main, "FundingOpenInterestAnalysis", Analysis)
    response = client.get(
        "/api/v1/analysis/derivatives/funding-open-interest/btcusdt",
        params={"period": "1h", "price_interval": "15m", "limit": 30},
    )
    assert response.status_code == 200
    assert response.json() == {
        "status": "COMPLETED", "symbol": "BTCUSDT",
        "period": "1h", "price_interval": "15m", "limit": 30,
    }


def test_combined_derivatives_analysis_rejects_invalid_limit():
    response = client.get(
        "/api/v1/analysis/derivatives/funding-open-interest/BTCUSDT",
        params={"limit": 1},
    )
    assert response.status_code == 422


def test_combined_derivatives_analysis_returns_422_for_bad_period(monkeypatch):
    response = client.get(
        "/api/v1/analysis/derivatives/funding-open-interest/BTCUSDT",
        params={"period": "2w"},
    )
    assert response.status_code == 422
