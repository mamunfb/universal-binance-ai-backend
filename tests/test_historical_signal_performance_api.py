from fastapi.testclient import TestClient

from app import main
from app.main import app
from app.services.advanced_derivatives_analysis import DerivativesSignalStore
from app.services.historical_klines import HistoricalKlineStore

client = TestClient(app)


def _candle(ts, close):
    return [ts, "100", str(max(100, close) + 2), "98", str(close),
            "10", ts + 3_599_999, "1000", 20, "4", "400", "0"]


def test_signal_performance_api_reads_local_snapshots_and_candles(monkeypatch, tmp_path):
    hour = 3_600_000
    signals = DerivativesSignalStore(str(tmp_path / "signals.sqlite3"))
    klines = HistoricalKlineStore(str(tmp_path / "klines.sqlite3"))
    klines.save_klines("USD_M", "BTCUSDT", "1h", [
        _candle(i * hour, 100 + i) for i in range(26)
    ])
    signals.save({
        "status": "COMPLETED", "symbol": "BTCUSDT", "period": "1h",
        "window": {"end_time_ms": hour},
        "positioning_context": {"classification": "PRICE_UP_OI_UP_BUILDUP_CANDIDATE"},
    })
    monkeypatch.setattr(main, "derivatives_signal_store", signals)
    monkeypatch.setattr(main, "historical_kline_store", klines)

    response = client.get(
        "/api/v1/analysis/derivatives/signal-performance/BTCUSDT",
        params={"round_trip_cost_bps": 10},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["horizons"]["1"]["sample_size"] == 1
    assert payload["horizons"]["1"]["mean_net_hypothetical_return_percent"] == 0.9


def test_signal_performance_api_validates_parameters():
    response = client.get(
        "/api/v1/analysis/derivatives/signal-performance/BTCUSDT",
        params={"round_trip_cost_bps": 501},
    )
    assert response.status_code == 422
