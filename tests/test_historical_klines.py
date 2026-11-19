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


@pytest.mark.parametrize("index,value", [
    (0, True), (0, 1.5), (6, True), (6, 1.5), (8, True), (8, 1.5),
    (1, True), (5, True),
])
def test_store_rejects_boolean_and_fractional_numeric_fields(tmp_path, index, value):
    row = candle()
    row[index] = value
    store = HistoricalKlineStore(str(tmp_path / "history.sqlite3"))
    with pytest.raises(ValueError):
        store.save_klines("SPOT", "BTCUSDT", "1m", [row])
    assert store.history("SPOT", "BTCUSDT", "1m")["returned_count"] == 0
