from fastapi.testclient import TestClient

from app import main
from app.main import app
from app.services.historical_klines import HistoricalKlineStore

client = TestClient(app)


def _candle(open_time):
    return [
        open_time, "100", "105", "99", "101", "10",
        open_time + 59_999, "1000", 25, "4", "400", "0",
    ]


def test_coverage_endpoint_reports_missing_candles(monkeypatch, tmp_path):
    db = str(tmp_path / "history.sqlite3")
    monkeypatch.setattr(main.settings, "historical_kline_database_path", db)
    store = HistoricalKlineStore(db)
    start = 1_700_000_040_000
    store.save_klines("SPOT", "BTCUSDT", "1m", [
        _candle(start), _candle(start + 120_000),
    ])

    response = client.get(
        "/api/v1/history/klines/SPOT/BTCUSDT/coverage",
        params={
            "interval": "1m",
            "start_time_ms": start,
            "end_time_ms": start + 120_000,
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "INCOMPLETE"
    assert response.json()["coverage"]["missing_candle_count"] == 1


def test_coverage_endpoint_requires_aligned_range(monkeypatch, tmp_path):
    monkeypatch.setattr(
        main.settings, "historical_kline_database_path",
        str(tmp_path / "history.sqlite3"),
    )
    response = client.get(
        "/api/v1/history/klines/SPOT/BTCUSDT/coverage",
        params={"interval": "1m", "start_time_ms": 1, "end_time_ms": 60_000},
    )
    assert response.status_code == 422
