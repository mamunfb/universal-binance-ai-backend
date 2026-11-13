import pytest

from app.services.historical_klines import HistoricalKlineStore


def candle(open_time=1700000000000, close="101"):
    return [
        open_time, "100", "105", "99", close, "10",
        open_time + 59999, "1000", 25, "4", "400", "0",
    ]


def test_store_saves_and_reads_candles_in_time_order(tmp_path):
    store = HistoricalKlineStore(str(tmp_path / "history.sqlite3"))
    result = store.save_klines("spot", "btcusdt", "1m", [candle(1700000060000), candle()])
    assert result["status"] == "COMPLETED"
    assert result["stored_count"] == 2
    history = store.history("SPOT", "BTCUSDT", "1m")
    assert history["returned_count"] == 2
    assert [row["open_time_ms"] for row in history["candles"]] == [
        1700000000000, 1700000060000
    ]
    assert history["candles"][0]["close"] == 101.0


def test_store_is_idempotent_for_same_candle_open_time(tmp_path):
    store = HistoricalKlineStore(str(tmp_path / "history.sqlite3"))
    store.save_klines("SPOT", "BTCUSDT", "1m", [candle()])
    result = store.save_klines("SPOT", "BTCUSDT", "1m", [candle(close="102")])
    history = store.history("SPOT", "BTCUSDT", "1m")
    assert result["total_stored_count"] == 1
    assert history["candles"][0]["close"] == 102.0


@pytest.mark.parametrize("row", [
    ["bad"], candle(close="nan"), candle(close="inf"),
    [1700000000000, "100", "98", "99", "101", "10",
     1700000059999, "1000", 25, "4", "400", "0"],
    [1700000000000, "100", "105", "99", "101", "3",
     1700000059999, "1000", 25, "4", "400", "0"],
])
def test_store_rejects_malformed_or_inconsistent_candles(tmp_path, row):
    store = HistoricalKlineStore(str(tmp_path / "history.sqlite3"))
    with pytest.raises(ValueError):
        store.save_klines("SPOT", "BTCUSDT", "1m", [row])
    assert store.history("SPOT", "BTCUSDT", "1m")["returned_count"] == 0


def test_store_rejects_duplicate_open_times_in_one_batch(tmp_path):
    store = HistoricalKlineStore(str(tmp_path / "history.sqlite3"))
    with pytest.raises(ValueError, match="Duplicate"):
        store.save_klines("SPOT", "BTCUSDT", "1m", [candle(), candle()])


def test_history_validates_bounds_and_market(tmp_path):
    store = HistoricalKlineStore(str(tmp_path / "history.sqlite3"))
    with pytest.raises(ValueError, match="market"):
        store.history("OTHER", "BTCUSDT", "1m")
    with pytest.raises(ValueError, match="end_time_ms"):
        store.history("SPOT", "BTCUSDT", "1m", 10, 5)
    with pytest.raises(ValueError, match="limit"):
        store.history("SPOT", "BTCUSDT", "1m", limit=5001)

@pytest.mark.parametrize("index", [0, 6, 8])
def test_store_rejects_boolean_integer_fields(tmp_path, index):
    row = candle()
    row[index] = True
    store = HistoricalKlineStore(str(tmp_path / "history.sqlite3"))
    with pytest.raises(ValueError):
        store.save_klines("SPOT", "BTCUSDT", "1m", [row])
    assert store.history("SPOT", "BTCUSDT", "1m")["returned_count"] == 0


@pytest.mark.parametrize("index", [1, 2, 3, 4, 5, 7, 9, 10])
def test_store_rejects_boolean_decimal_fields(tmp_path, index):
    row = candle()
    row[index] = True
    store = HistoricalKlineStore(str(tmp_path / "history.sqlite3"))
    with pytest.raises(ValueError):
        store.save_klines("SPOT", "BTCUSDT", "1m", [row])
    assert store.history("SPOT", "BTCUSDT", "1m")["returned_count"] == 0


@pytest.mark.parametrize("index", [0, 6, 8])
def test_store_rejects_fractional_integer_fields(tmp_path, index):
    row = candle()
    row[index] = float(row[index]) + 0.5
    store = HistoricalKlineStore(str(tmp_path / "history.sqlite3"))
    with pytest.raises(ValueError):
        store.save_klines("SPOT", "BTCUSDT", "1m", [row])
    assert store.history("SPOT", "BTCUSDT", "1m")["returned_count"] == 0


def test_older_request_observation_cannot_overwrite_newer_candle(tmp_path):
    store = HistoricalKlineStore(str(tmp_path / "history.sqlite3"))
    # The newer request finishes and commits first; an older, slower request
    # finishes later. The UPSERT must preserve the newer observation.
    store.save_klines(
        "SPOT", "BTCUSDT", "1m", [candle(close="102")],
        observation_started_at_ns=2_000,
    )
    store.save_klines(
        "SPOT", "BTCUSDT", "1m", [candle(close="101")],
        observation_started_at_ns=1_000,
    )
    saved = store.history("SPOT", "BTCUSDT", "1m")
    assert saved["candles"][0]["close"] == 102.0
    assert saved["candles"][0]["observation_started_at_ns"] == 2_000


def test_newer_request_observation_updates_existing_candle(tmp_path):
    store = HistoricalKlineStore(str(tmp_path / "history.sqlite3"))
    store.save_klines(
        "SPOT", "BTCUSDT", "1m", [candle(close="101")],
        observation_started_at_ns=1_000,
    )
    store.save_klines(
        "SPOT", "BTCUSDT", "1m", [candle(close="103")],
        observation_started_at_ns=3_000,
    )
    saved = store.history("SPOT", "BTCUSDT", "1m")
    assert saved["candles"][0]["close"] == 103.0
    assert saved["candles"][0]["observation_started_at_ns"] == 3_000


def test_legacy_sqlite_rows_with_unknown_observation_can_be_refreshed(tmp_path):
    import sqlite3

    database = str(tmp_path / "legacy.sqlite3")
    with sqlite3.connect(database) as connection:
        connection.execute("""
            CREATE TABLE historical_klines (
                market TEXT NOT NULL, symbol TEXT NOT NULL, interval TEXT NOT NULL,
                open_time_ms INTEGER NOT NULL, open REAL NOT NULL, high REAL NOT NULL,
                low REAL NOT NULL, close REAL NOT NULL, volume REAL NOT NULL,
                close_time_ms INTEGER NOT NULL, quote_volume REAL NOT NULL,
                trade_count INTEGER NOT NULL, taker_buy_base_volume REAL NOT NULL,
                taker_buy_quote_volume REAL NOT NULL, source TEXT NOT NULL,
                collected_at TEXT NOT NULL,
                PRIMARY KEY (market, symbol, interval, open_time_ms)
            )
        """)
        connection.execute("""
            INSERT INTO historical_klines VALUES (
                'SPOT', 'BTCUSDT', '1m', 1700000000000,
                100, 105, 99, 100, 10, 1700000059999,
                1000, 25, 4, 400, 'legacy', '2026-01-01T00:00:00+00:00'
            )
        """)

    store = HistoricalKlineStore(database)
    store.save_klines(
        "SPOT", "BTCUSDT", "1m", [candle(close="104")],
        observation_started_at_ns=4_000,
    )
    saved = store.history("SPOT", "BTCUSDT", "1m")
    assert saved["candles"][0]["close"] == 104.0
    assert saved["candles"][0]["observation_started_at_ns"] == 4_000


@pytest.mark.parametrize("token", [True, -1, 1.5, "100"])
def test_store_rejects_invalid_observation_order_token(tmp_path, token):
    store = HistoricalKlineStore(str(tmp_path / "history.sqlite3"))
    with pytest.raises(ValueError, match="observation_started_at_ns"):
        store.save_klines(
            "SPOT", "BTCUSDT", "1m", [candle()],
            observation_started_at_ns=token,
        )


def test_postgres_upsert_only_accepts_newer_observation(monkeypatch):
    from app.services import historical_klines as module

    class FakeConnection:
        def __init__(self):
            self.executemany_query = ""
            self.executemany_values = None

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def cursor(self):
            return self

        def executemany(self, query, values):
            self.executemany_query = query
            self.executemany_values = values

        def execute(self, query, params):
            class Result:
                def fetchone(self):
                    return {"count": 1}
            return Result()

    connection = FakeConnection()
    monkeypatch.setattr(module.psycopg, "connect", lambda *_a, **_kw: connection)
    store = HistoricalKlineStore("unused.sqlite3", "postgresql://example.invalid/db")
    result = store.save_klines(
        "SPOT", "BTCUSDT", "1m", [candle(close="102")],
        observation_started_at_ns=5_000,
    )
    assert result["storage"] == "POSTGRESQL"
    assert connection.executemany_query.count("%s") == 17
    assert len(connection.executemany_values[0]) == 17
    assert "ON CONFLICT(market, symbol, interval, open_time_ms) DO UPDATE SET" in connection.executemany_query
    assert "WHERE public.historical_klines.observation_started_at_ns IS NULL" in connection.executemany_query
    assert "excluded.observation_started_at_ns > public.historical_klines.observation_started_at_ns" in connection.executemany_query

def test_postgres_store_preserves_newer_observation_after_out_of_order_writes():
    import os
    import uuid
    import pytest

    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is not configured")
    from app.services.historical_klines import HistoricalKlineStore
    import psycopg

    symbol = f"OBS{uuid.uuid4().hex[:20].upper()}"
    store = HistoricalKlineStore("unused.sqlite3", database_url)
    try:
        store.save_klines(
            "SPOT", symbol, "1m", [candle(close="102")],
            observation_started_at_ns=20_000,
        )
        store.save_klines(
            "SPOT", symbol, "1m", [candle(close="101")],
            observation_started_at_ns=10_000,
        )
        history = store.history("SPOT", symbol, "1m")
        assert history["candles"][0]["close"] == 102.0
        assert history["candles"][0]["observation_started_at_ns"] == 20_000
    finally:
        with psycopg.connect(database_url) as connection:
            connection.execute(
                "DELETE FROM public.historical_klines WHERE market=%s AND symbol=%s AND interval=%s",
                ("SPOT", symbol, "1m"),
            )
