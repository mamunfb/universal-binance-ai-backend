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
    event(timestamp=True),
    event(rate=True),
    event(mark=True),
])
def test_funding_store_rejects_boolean_values(tmp_path, row):
    store = FundingRateStore(str(tmp_path / "funding.sqlite3"))
    with pytest.raises(ValueError):
        store.save("USD_M", "BTCUSDT", [row])
    assert store.history("USD_M", "BTCUSDT")["returned_count"] == 0


@pytest.mark.parametrize("timestamp", [1700000000000.5, "1700000000000.5", "1e3"])
def test_funding_store_rejects_fractional_timestamps(tmp_path, timestamp):
    store = FundingRateStore(str(tmp_path / "funding.sqlite3"))
    with pytest.raises(ValueError, match="timestamp"):
        store.save("USD_M", "BTCUSDT", [event(timestamp=timestamp)])
    assert store.history("USD_M", "BTCUSDT")["returned_count"] == 0
