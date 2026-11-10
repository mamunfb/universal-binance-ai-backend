from fastapi.testclient import TestClient

from app import main
from app.main import app

client = TestClient(app)


def test_advanced_derivatives_endpoint_wires_all_local_stores(monkeypatch):
    class Engine:
        def __init__(self, funding, oi, klines, liquidations, signals):
            assert funding is main.funding_rate_store
            assert oi is main.open_interest_store
            assert klines is main.historical_kline_store
            assert liquidations is main.liquidation_store
            assert signals is main.derivatives_signal_store

        def analyze(self, *args):
            return {"status": "COMPLETED", "args": args}

    monkeypatch.setattr(main, "AdvancedDerivativesAnalysis", Engine)
    response = client.get(
        "/api/v1/analysis/derivatives/advanced/BTCUSDT",
        params={"period": "1h", "price_interval": "15m", "limit": 24,
                "funding_abs_threshold": 0.002, "spike_mad_multiplier": 4},
    )
    assert response.status_code == 200
    assert response.json()["args"] == ["BTCUSDT", "1h", "15m", 24, 0.002, 4]


def test_advanced_derivatives_endpoint_rejects_bad_query():
    response = client.get(
        "/api/v1/analysis/derivatives/advanced/BTCUSDT",
        params={"period": "2w", "limit": 5},
    )
    assert response.status_code == 422


def test_derivatives_signal_history_endpoint_uses_store(monkeypatch):
    calls = []

    def fake_history(*args):
        calls.append(args)
        return {"status": "COMPLETED", "symbol": "BTCUSDT"}

    monkeypatch.setattr(main.derivatives_signal_store, "history", fake_history)
    response = client.get(
        "/api/v1/history/derivatives-signals/btcusdt",
        params={"period": "1h", "start_time_ms": 10, "end_time_ms": 20, "limit": 25},
    )
    assert response.status_code == 200
    assert calls == [("btcusdt", "1h", 10, 20, 25)]
