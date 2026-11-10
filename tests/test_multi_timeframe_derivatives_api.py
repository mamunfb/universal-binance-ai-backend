from fastapi.testclient import TestClient

from app import main
from app.main import app

client = TestClient(app)


def test_multi_timeframe_endpoint_uses_requested_periods(monkeypatch):
    calls = []

    class FakeMulti:
        def __init__(self, engine):
            assert isinstance(engine, main.AdvancedDerivativesAnalysis)

        def analyze(self, symbol, periods, limit):
            calls.append((symbol, periods, limit))
            return {"status": "COMPLETED", "periods": periods}

    monkeypatch.setattr(main, "MultiTimeframeDerivativesAnalysis", FakeMulti)
    response = client.get(
        "/api/v1/analysis/derivatives/multi-timeframe/BTCUSDT",
        params={"periods": "5m,1h,4h", "limit": 24},
    )
    assert response.status_code == 200
    assert response.json()["periods"] == ["5m", "1h", "4h"]
    assert calls == [("BTCUSDT", ["5m", "1h", "4h"], 24)]


def test_multi_timeframe_endpoint_rejects_bad_limit():
    response = client.get(
        "/api/v1/analysis/derivatives/multi-timeframe/BTCUSDT",
        params={"limit": 5},
    )
    assert response.status_code == 422


def test_multi_timeframe_endpoint_rejects_bad_period():
    response = client.get(
        "/api/v1/analysis/derivatives/multi-timeframe/BTCUSDT",
        params={"periods": "1m"},
    )
    assert response.status_code == 422
