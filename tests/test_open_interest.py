import pytest

from app.services.open_interest import OpenInterestStore


def record(timestamp=1700000000000, amount="123.45", value="4567890.12", supply="19000000"):
    return {
        "symbol": "BTCUSDT", "timestamp": timestamp,
        "sumOpenInterest": amount, "sumOpenInterestValue": value,
        "CMCCirculatingSupply": supply,
    }


def test_open_interest_store_saves_and_reads_time_order(tmp_path):
    store = OpenInterestStore(str(tmp_path / "oi.sqlite3"))
    result = store.save("USD_M", "btcusdt", "1h", [record(1700003600000), record()])
    assert result["stored_count"] == 2
    history = store.history("USD_M", "BTCUSDT", "1h")
    assert [x["timestamp_ms"] for x in history["records"]] == [
        1700000000000, 1700003600000
    ]
    assert history["records"][0]["sum_open_interest"] == 123.45
    assert history["coverage"]["expected_schedule_verified"] is False


def test_open_interest_store_upserts_same_timestamp(tmp_path):
    store = OpenInterestStore(str(tmp_path / "oi.sqlite3"))
    store.save("USD_M", "BTCUSDT", "1h", [record()])
    result = store.save("USD_M", "BTCUSDT", "1h", [record(amount="124")])
    history = store.history("USD_M", "BTCUSDT", "1h")
    assert result["total_stored_count"] == 1
    assert history["records"][0]["sum_open_interest"] == 124.0


def test_open_interest_periods_are_separate_series(tmp_path):
    store = OpenInterestStore(str(tmp_path / "oi.sqlite3"))
    store.save("USD_M", "BTCUSDT", "1h", [record()])
    store.save("USD_M", "BTCUSDT", "5m", [record()])
    assert store.history("USD_M", "BTCUSDT", "1h")["returned_count"] == 1
    assert store.history("USD_M", "BTCUSDT", "5m")["returned_count"] == 1


@pytest.mark.parametrize("row", [
    {"symbol": "BTCUSDT", "timestamp": -1, "sumOpenInterest": "1", "sumOpenInterestValue": "2"},
    record(amount="nan"),
    record(value="inf"),
    record(supply="-1"),
    {"symbol": "BTCUSDT", "sumOpenInterest": "1", "sumOpenInterestValue": "2"},
])
def test_open_interest_store_rejects_invalid_records(tmp_path, row):
    store = OpenInterestStore(str(tmp_path / "oi.sqlite3"))
    with pytest.raises(ValueError):
        store.save("USD_M", "BTCUSDT", "1h", [row])
    assert store.history("USD_M", "BTCUSDT", "1h")["returned_count"] == 0


def test_open_interest_store_rejects_duplicate_timestamp_symbol_mismatch_and_market(tmp_path):
    store = OpenInterestStore(str(tmp_path / "oi.sqlite3"))
    with pytest.raises(ValueError, match="Duplicate"):
        store.save("USD_M", "BTCUSDT", "1h", [record(), record()])
    with pytest.raises(ValueError, match="symbol"):
        store.save("USD_M", "BTCUSDT", "1h", [record() | {"symbol": "ETHUSDT"}])
    with pytest.raises(ValueError, match="USD_M"):
        store.save("COIN_M", "BTCUSD_PERP", "1h", [record()])


def test_open_interest_history_validates_period_bounds_and_limit(tmp_path):
    store = OpenInterestStore(str(tmp_path / "oi.sqlite3"))
    with pytest.raises(ValueError, match="period"):
        store.history("USD_M", "BTCUSDT", "2w")
    with pytest.raises(ValueError, match="end_time_ms"):
        store.history("USD_M", "BTCUSDT", "1h", 20, 10)
    with pytest.raises(ValueError, match="limit"):
        store.history("USD_M", "BTCUSDT", "1h", limit=5001)


@pytest.mark.parametrize("row", [
    record(timestamp=True), record(timestamp=1.5),
    record(amount=True), record(value=True), record(supply=True),
])
def test_open_interest_store_rejects_boolean_and_fractional_numeric_fields(tmp_path, row):
    store = OpenInterestStore(str(tmp_path / "oi.sqlite3"))
    with pytest.raises(ValueError):
        store.save("USD_M", "BTCUSDT", "1h", [row])
    assert store.history("USD_M", "BTCUSDT", "1h")["returned_count"] == 0
