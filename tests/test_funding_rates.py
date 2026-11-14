import pytest

from app.services.funding_rates import FundingRateStore


def event(timestamp=1700000000000, rate="0.0001", mark="37000"):
    return {"symbol": "BTCUSDT", "fundingTime": timestamp,
            "fundingRate": rate, "markPrice": mark}


def test_funding_store_saves_and_reads_events_in_time_order(tmp_path):
    store = FundingRateStore(str(tmp_path / "funding.sqlite3"))
    result = store.save("USD_M", "btcusdt", [event(1700000280000), event()])
    assert result["stored_count"] == 2
    history = store.history("USD_M", "BTCUSDT")
    assert [x["funding_time_ms"] for x in history["events"]] == [
        1700000000000, 1700000280000
    ]
    assert history["events"][0]["funding_rate"] == 0.0001
    assert history["coverage"]["expected_schedule_verified"] is False
    assert history["coverage"]["observed_event_gaps"][0]["observed_gap_ms"] == 280000


def test_funding_store_upserts_same_event_idempotently(tmp_path):
    store = FundingRateStore(str(tmp_path / "funding.sqlite3"))
    store.save("USD_M", "BTCUSDT", [event()])
    result = store.save("USD_M", "BTCUSDT", [event(rate="0.0002")])
    history = store.history("USD_M", "BTCUSDT")
    assert result["total_stored_count"] == 1
    assert history["events"][0]["funding_rate"] == 0.0002


@pytest.mark.parametrize("row", [
    {"fundingTime": -1, "fundingRate": "0.1"},
    {"fundingTime": 10, "fundingRate": "nan"},
    {"fundingTime": 10, "fundingRate": "0.1", "markPrice": "inf"},
    {"fundingRate": "0.1"},
])
def test_funding_store_rejects_invalid_rows(tmp_path, row):
    store = FundingRateStore(str(tmp_path / "funding.sqlite3"))
    with pytest.raises(ValueError):
        store.save("USD_M", "BTCUSDT", [row])
    assert store.history("USD_M", "BTCUSDT")["returned_count"] == 0


def test_funding_store_rejects_lease_with_sqlite_storage(tmp_path):
    store = FundingRateStore(str(tmp_path / "funding.sqlite3"))
    with pytest.raises(ValueError, match="PostgreSQL"):
        store.save("USD_M", "BTCUSDT", [event()], lease=object())


def test_funding_store_rejects_symbol_mismatch(tmp_path):
    store = FundingRateStore(str(tmp_path / "funding.sqlite3"))
    with pytest.raises(ValueError, match="symbol"):
        store.save("USD_M", "BTCUSDT", [event() | {"symbol": "ETHUSDT"}])


def test_funding_store_rejects_duplicate_timestamps_and_wrong_market(tmp_path):
    store = FundingRateStore(str(tmp_path / "funding.sqlite3"))
    with pytest.raises(ValueError, match="Duplicate"):
        store.save("USD_M", "BTCUSDT", [event(), event()])
    with pytest.raises(ValueError, match="USD_M"):
        store.save("COIN_M", "BTCUSD_PERP", [event()])


def test_funding_history_validates_bounds_and_limit(tmp_path):
    store = FundingRateStore(str(tmp_path / "funding.sqlite3"))
    with pytest.raises(ValueError, match="end_time_ms"):
        store.history("USD_M", "BTCUSDT", 20, 10)
    with pytest.raises(ValueError, match="limit"):
        store.history("USD_M", "BTCUSDT", limit=5001)

@pytest.mark.parametrize("row", [
    event(timestamp=True),
    event(rate=True),
    event(mark=True),
])
def test_funding_store_rejects_boolean_values(tmp_path, row):
    store = FundingRateStore(str(tmp_path / "funding.sqlite3"))
    with pytest.raises(ValueError):
        store.save("USD_M", "BTCUSDT", [row])
    assert store.history("USD_M", "BTCUSDT")["returned_count"] == 0
