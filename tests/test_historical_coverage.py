import pytest

from app.services.historical_coverage import HistoricalCoverageEngine
from app.services.historical_klines import HistoricalKlineStore


def candle(open_time):
    return [
        open_time, "100", "105", "99", "101", "10",
        open_time + 59_999, "1000", 25, "4", "400", "0",
    ]


def test_reports_missing_candle_and_groups_contiguous_gap(tmp_path):
    db = str(tmp_path / "history.sqlite3")
    store = HistoricalKlineStore(db)
    minute = 60_000
    start = 1_700_000_040_000  # UTC minute boundary
    store.save_klines("SPOT", "BTCUSDT", "1m", [
        candle(start), candle(start + 3 * minute), candle(start + 4 * minute),
    ])

    result = HistoricalCoverageEngine(db).inspect(
        "SPOT", "BTCUSDT", "1m", start, start + 4 * minute
    )
    assert result["status"] == "INCOMPLETE"
    assert result["coverage"]["expected_candle_count"] == 5
    assert result["coverage"]["stored_candle_count"] == 3
    assert result["coverage"]["missing_candle_count"] == 2
    assert result["coverage"]["coverage_ratio"] == 0.6
    assert result["coverage"]["gaps"] == [{
        "start_open_time_ms": start + minute,
        "end_open_time_ms": start + 2 * minute,
        "missing_count": 2,
    }]


def test_reports_complete_range(tmp_path):
    db = str(tmp_path / "history.sqlite3")
    store = HistoricalKlineStore(db)
    start = 1_700_000_040_000
    store.save_klines("SPOT", "BTCUSDT", "1m", [
        candle(start), candle(start + 60_000),
    ])
    result = HistoricalCoverageEngine(db).inspect(
        "SPOT", "BTCUSDT", "1m", start, start + 60_000
    )
    assert result["status"] == "COMPLETE"
    assert result["coverage"]["contiguous"] is True
    assert result["coverage"]["gaps"] == []


def test_reports_no_stored_data(tmp_path):
    db = str(tmp_path / "history.sqlite3")
    HistoricalKlineStore(db)
    start = 1_700_000_040_000
    result = HistoricalCoverageEngine(db).inspect(
        "SPOT", "BTCUSDT", "1m", start, start + 60_000
    )
    assert result["status"] == "NO_STORED_DATA"
    assert result["coverage"]["missing_candle_count"] == 2


@pytest.mark.parametrize("market,symbol,interval,start,end", [
    ("BAD", "BTCUSDT", "1m", 0, 60_000),
    ("SPOT", "", "1m", 0, 60_000),
    ("SPOT", "BTCUSDT", "2w", 0, 60_000),
    ("SPOT", "BTCUSDT", "1m", 1, 60_000),
    ("SPOT", "BTCUSDT", "1m", 60_000, 0),
])
def test_rejects_invalid_coverage_request(tmp_path, market, symbol, interval, start, end):
    db = str(tmp_path / "history.sqlite3")
    HistoricalKlineStore(db)
    with pytest.raises(ValueError):
        HistoricalCoverageEngine(db).inspect(market, symbol, interval, start, end)


def test_monthly_interval_uses_calendar_month_boundaries(tmp_path):
    db = str(tmp_path / "history.sqlite3")
    HistoricalKlineStore(db)
    jan = 1_704_067_200_000  # 2024-01-01T00:00:00Z
    mar = 1_709_251_200_000  # 2024-03-01T00:00:00Z
    result = HistoricalCoverageEngine(db).inspect(
        "SPOT", "BTCUSDT", "1M", jan, mar
    )
    assert result["coverage"]["expected_candle_count"] == 3
    assert result["coverage"]["missing_candle_count"] == 3


def test_rejects_ranges_above_safety_limit(tmp_path):
    db = str(tmp_path / "history.sqlite3")
    HistoricalKlineStore(db)
    with pytest.raises(ValueError, match="exceeds"):
        HistoricalCoverageEngine(db, max_expected_candles=2).inspect(
            "SPOT", "BTCUSDT", "1m", 0, 120_000
        )


def test_postgres_coverage_reads_configured_database_without_sqlite(tmp_path, monkeypatch):
    from app.services import historical_coverage as module

    start = 1_700_000_040_000
    calls = []

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, query, params):
            calls.append((query, params))
            self.rows = [(start,), (start + 60_000,)]
            return self

        def fetchall(self):
            return self.rows

    monkeypatch.setattr(module.psycopg, "connect", lambda *_a, **_kw: FakeConnection())
    result = HistoricalCoverageEngine(
        str(tmp_path / "unused.sqlite3"),
        database_url="postgresql://example.invalid/test",
    ).inspect("SPOT", "BTCUSDT", "1m", start, start + 60_000)

    assert result["status"] == "COMPLETE"
    assert result["source"] == "Neon PostgreSQL historical candle store"
    assert calls[0][0].count("%s") == 5
    assert calls[0][1] == ("SPOT", "BTCUSDT", "1m", start, start + 60_000)
    assert not (tmp_path / "unused.sqlite3").exists()
