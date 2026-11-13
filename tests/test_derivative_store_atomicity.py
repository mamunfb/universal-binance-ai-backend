import pytest

from app.services.funding_rates import FundingRateStore
from app.services.open_interest import OpenInterestStore


def test_funding_batch_rolls_back_when_database_rejects_a_row(tmp_path):
    store = FundingRateStore(str(tmp_path / "funding.sqlite3"))
    import sqlite3
    with sqlite3.connect(store.database_path) as connection:
        connection.execute("""
            CREATE TRIGGER reject_funding_row
            BEFORE INSERT ON historical_funding_rates
            WHEN NEW.funding_time_ms = 1700000001000
            BEGIN
                SELECT RAISE(ABORT, 'injected row failure');
            END
        """)

    rows = [
        {"symbol": "BTCUSDT", "fundingTime": 1700000000000,
         "fundingRate": "0.0001", "markPrice": "37000"},
        {"symbol": "BTCUSDT", "fundingTime": 1700000001000,
         "fundingRate": "0.0002", "markPrice": "37001"},
    ]
    with pytest.raises(sqlite3.IntegrityError, match="injected row failure"):
        store.save("USD_M", "BTCUSDT", rows)

    assert store.history("USD_M", "BTCUSDT")["returned_count"] == 0


def test_open_interest_batch_rolls_back_when_database_rejects_a_row(tmp_path):
    store = OpenInterestStore(str(tmp_path / "oi.sqlite3"))
    import sqlite3
    with sqlite3.connect(store.database_path) as connection:
        connection.execute("""
            CREATE TRIGGER reject_oi_row
            BEFORE INSERT ON historical_open_interest
            WHEN NEW.timestamp_ms = 1700000001000
            BEGIN
                SELECT RAISE(ABORT, 'injected row failure');
            END
        """)

    def record(timestamp):
        return {
            "symbol": "BTCUSDT", "timestamp": timestamp,
            "sumOpenInterest": "10", "sumOpenInterestValue": "1000",
        }

    with pytest.raises(sqlite3.IntegrityError, match="injected row failure"):
        store.save("USD_M", "BTCUSDT", "1h", [record(1700000000000), record(1700000001000)])

    assert store.history("USD_M", "BTCUSDT", "1h")["returned_count"] == 0
