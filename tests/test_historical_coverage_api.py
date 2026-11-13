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


def test_coverage_endpoint_prefers_dedicated_historical_database_url(monkeypatch, tmp_path):
    captured = {}

    class FakeCoverageEngine:
        def __init__(self, database_path, database_url=""):
            captured["database_path"] = database_path
            captured["database_url"] = database_url

        def inspect(self, market, symbol, interval, start_time_ms, end_time_ms):
            return {"status": "COMPLETED"}

    monkeypatch.setattr(
        main.settings, "historical_kline_database_path",
        str(tmp_path / "unused.sqlite3"),
    )
    monkeypatch.setattr(
        main.settings, "database_url", "postgresql://shared.example/db",
    )
    monkeypatch.setattr(
        main.settings, "historical_kline_database_url",
        "postgresql://history.example/db",
    )
    monkeypatch.setattr(main, "HistoricalCoverageEngine", FakeCoverageEngine)

    response = client.get(
        "/api/v1/history/klines/SPOT/BTCUSDT/coverage",
        params={
            "interval": "1m",
            "start_time_ms": 1_700_000_040_000,
            "end_time_ms": 1_700_000_100_000,
        },
    )

    assert response.status_code == 200
    assert response.json() == {"status": "COMPLETED"}
    assert captured["database_url"] == "postgresql://history.example/db"
