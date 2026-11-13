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


@pytest.mark.parametrize("index,value", [
    (0, 1700000000000.5),
    (6, 1700000059999.5),
    (8, 25.5),
    (0, "1700000000000.5"),
    (6, "1700000059999.5"),
    (8, "25.5"),
])
def test_store_rejects_fractional_integer_fields(tmp_path, index, value):
    row = candle()
    row[index] = value
    store = HistoricalKlineStore(str(tmp_path / "history.sqlite3"))
    with pytest.raises(ValueError):
        store.save_klines("SPOT", "BTCUSDT", "1m", [row])
    assert store.history("SPOT", "BTCUSDT", "1m")["returned_count"] == 0


@pytest.mark.parametrize("index,value", [
    (0, "1700000000000"),
    (6, "1700000059999"),
    (8, "25"),
])
def test_store_accepts_integer_string_fields(tmp_path, index, value):
    row = candle()
    row[index] = value
    store = HistoricalKlineStore(str(tmp_path / "history.sqlite3"))
    result = store.save_klines("SPOT", "BTCUSDT", "1m", [row])
    assert result["stored_count"] == 1


@pytest.mark.parametrize("kwargs", [
    {"start_time_ms": 10.5},
    {"start_time_ms": "10.5"},
    {"end_time_ms": 20.5},
    {"end_time_ms": "20.5"},
    {"limit": 1.5},
    {"limit": "1.5"},
    {"start_time_ms": True},
    {"end_time_ms": False},
    {"limit": True},
])
def test_history_rejects_non_integer_query_values(tmp_path, kwargs):
    store = HistoricalKlineStore(str(tmp_path / "history.sqlite3"))
    with pytest.raises(ValueError):
        store.history("SPOT", "BTCUSDT", "1m", **kwargs)


def test_history_accepts_integer_string_query_values(tmp_path):
    store = HistoricalKlineStore(str(tmp_path / "history.sqlite3"))
    store.save_klines("SPOT", "BTCUSDT", "1m", [candle()])
    result = store.history(
        "SPOT", "BTCUSDT", "1m",
        start_time_ms="1700000000000", end_time_ms="1700000000000", limit="10",
    )
    assert result["returned_count"] == 1


@pytest.mark.parametrize("market,symbol,interval", [
    (None, "BTCUSDT", "1m"),
    (1, "BTCUSDT", "1m"),
    ("SPOT", None, "1m"),
    ("SPOT", "BTCUSDT", None),
])
def test_latest_open_time_rejects_invalid_query_types(tmp_path, market, symbol, interval):
    store = HistoricalKlineStore(str(tmp_path / "history.sqlite3"))
    with pytest.raises(ValueError):
        store.latest_open_time(market, symbol, interval)


@pytest.mark.parametrize("market,symbol,interval,source", [
    (None, "BTCUSDT", "1m", "test"),
    (1, "BTCUSDT", "1m", "test"),
    ("SPOT", None, "1m", "test"),
    ("SPOT", "BTCUSDT", None, "test"),
    ("SPOT", "BTCUSDT", "1m", None),
    ("SPOT", "BTCUSDT", "1m", ""),
])
def test_save_klines_rejects_invalid_metadata_types(tmp_path, market, symbol, interval, source):
    store = HistoricalKlineStore(str(tmp_path / "history.sqlite3"))
    with pytest.raises(ValueError):
        store.save_klines(market, symbol, interval, [candle()], source=source)
    assert store.history("SPOT", "BTCUSDT", "1m")["returned_count"] == 0


@pytest.mark.parametrize("index", [1, 2, 3, 4, 5, 7, 9, 10])
def test_store_rejects_boolean_candle_metrics(tmp_path, index):
    row = candle()
    row[index] = True
    store = HistoricalKlineStore(str(tmp_path / "history.sqlite3"))
    with pytest.raises(ValueError):
        store.save_klines("SPOT", "BTCUSDT", "1m", [row])
    assert store.history("SPOT", "BTCUSDT", "1m")["returned_count"] == 0


@pytest.mark.parametrize("index,value", [
    (0, 2**63),
    (6, 2**63),
    (8, 2**63),
])
def test_store_rejects_integer_fields_outside_storage_range(tmp_path, index, value):
    row = candle()
    row[index] = value
    store = HistoricalKlineStore(str(tmp_path / "history.sqlite3"))
    with pytest.raises(ValueError, match="signed 64-bit"):
        store.save_klines("SPOT", "BTCUSDT", "1m", [row])
    assert store.history("SPOT", "BTCUSDT", "1m")["returned_count"] == 0


@pytest.mark.parametrize("kwargs", [
    {"start_time_ms": 2**63},
    {"end_time_ms": 2**63},
])
def test_history_rejects_query_bounds_outside_storage_range(tmp_path, kwargs):
    store = HistoricalKlineStore(str(tmp_path / "history.sqlite3"))
    with pytest.raises(ValueError, match="signed 64-bit"):
        store.history("SPOT", "BTCUSDT", "1m", **kwargs)


def test_postgres_adapter_save_upsert_history_and_latest(tmp_path, monkeypatch):
    from app.services import historical_klines as module

    stored = {}

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def cursor(self):
            return self

        def executemany(self, query, values):
            assert "ON CONFLICT(market, symbol, interval, open_time_ms) DO UPDATE" in query
            for row in values:
                stored[(row[0], row[1], row[2], row[3])] = {
                    "market": row[0], "symbol": row[1], "interval": row[2],
                    "open_time_ms": row[3], "open": row[4], "high": row[5],
                    "low": row[6], "close": row[7], "volume": row[8],
                    "close_time_ms": row[9], "quote_volume": row[10],
                    "trade_count": row[11], "taker_buy_base_volume": row[12],
                    "taker_buy_quote_volume": row[13], "source": row[14],
                    "collected_at": row[15],
                }

        def execute(self, query, params):
            if "SELECT COUNT(*) AS count" in query:
                self.result = {"count": sum(1 for key in stored if key[:3] == tuple(params))}
            elif "SELECT MAX(open_time_ms) AS latest" in query:
                matches = [key[3] for key in stored if key[:3] == tuple(params)]
                self.result = {"latest": max(matches) if matches else None}
            elif "FROM public.historical_klines WHERE" in query:
                market, symbol, interval = params[:3]
                start = params[3] if len(params) > 4 else None
                end = params[4] if len(params) > 5 else None
                limit = params[-1]
                rows = [
                    value for key, value in stored.items()
                    if key[:3] == (market, symbol, interval)
                    and (start is None or key[3] >= start)
                    and (end is None or key[3] <= end)
                ]
                self.results = sorted(rows, key=lambda item: item["open_time_ms"], reverse=True)[:limit]
            else:
                raise AssertionError(f"Unexpected SQL: {query}")
            return self

        def fetchone(self):
            return self.result

        def fetchall(self):
            return self.results

    monkeypatch.setattr(module.psycopg, "connect", lambda *_a, **_kw: FakeConnection())
    store = HistoricalKlineStore(
        str(tmp_path / "unused.sqlite3"), "postgresql://example.invalid/db"
    )
    first = store.save_klines("spot", "btcusdt", "1m", [candle()])
    updated = store.save_klines("SPOT", "BTCUSDT", "1m", [candle(close="102")])
    history = store.history("SPOT", "BTCUSDT", "1m")
    latest = store.latest_open_time("SPOT", "BTCUSDT", "1m")

    assert first["storage"] == "POSTGRESQL"
    assert updated["total_stored_count"] == 1
    assert history["returned_count"] == 1
    assert history["candles"][0]["close"] == 102.0
    assert latest == 1700000000000
    assert not (tmp_path / "unused.sqlite3").exists()
