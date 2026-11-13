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
