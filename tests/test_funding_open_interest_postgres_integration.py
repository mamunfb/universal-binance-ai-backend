"""Opt-in real PostgreSQL integration tests for funding and open-interest stores.

Use only a disposable Neon branch/database with migrations/003_funding_and_open_interest.sql applied.
"""
import os
import time
import uuid

import pytest

from app.services.funding_rates import FundingRateStore
from app.services.open_interest import OpenInterestStore


@pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL is not configured; PostgreSQL integration tests skipped",
)
def test_real_postgres_funding_and_open_interest_save_read_cleanup(tmp_path):
    database_url = os.environ["TEST_DATABASE_URL"]
    suffix = uuid.uuid4().hex[:12].upper()
    funding_symbol = f"FUND{suffix}"
    oi_symbol = f"OPEN{suffix}"
    timestamp = int(time.time() * 1000) - 120_000
    funding = FundingRateStore(str(tmp_path / "unused-funding.sqlite3"), database_url)
    open_interest = OpenInterestStore(str(tmp_path / "unused-oi.sqlite3"), database_url)

    try:
        funding_result = funding.save("USD_M", funding_symbol, [{
            "symbol": funding_symbol, "fundingTime": timestamp,
            "fundingRate": "0.0001", "markPrice": "100",
        }], source="POSTGRES_INTEGRATION_TEST")
        assert funding_result["storage"] == "POSTGRESQL"
        funding_history = funding.history("USD_M", funding_symbol)
        assert funding_history["returned_count"] == 1
        assert funding_history["events"][0]["funding_time_ms"] == timestamp
        assert funding_history["source"].startswith("Neon PostgreSQL")

        oi_result = open_interest.save("USD_M", oi_symbol, "1h", [{
            "symbol": oi_symbol, "timestamp": timestamp,
            "sumOpenInterest": "10", "sumOpenInterestValue": "1000",
            "CMCCirculatingSupply": "20",
        }], source="POSTGRES_INTEGRATION_TEST")
        assert oi_result["storage"] == "POSTGRESQL"
        oi_history = open_interest.history("USD_M", oi_symbol, "1h")
        assert oi_history["returned_count"] == 1
        assert oi_history["records"][0]["timestamp_ms"] == timestamp
        assert oi_history["source"].startswith("Neon PostgreSQL")
    finally:
        with funding._connect_postgres() as connection:
            connection.execute(
                "DELETE FROM public.historical_funding_rates WHERE market=%s AND symbol=%s",
                ("USD_M", funding_symbol),
            )
        with open_interest._connect_postgres() as connection:
            connection.execute(
                "DELETE FROM public.historical_open_interest WHERE market=%s AND symbol=%s",
                ("USD_M", oi_symbol),
            )
