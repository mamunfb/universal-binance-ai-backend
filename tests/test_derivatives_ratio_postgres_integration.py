"""Opt-in PostgreSQL integration test for derivatives ratio history."""
import os
import time
import uuid

import pytest

from app.services.derivatives_ratio_store import DerivativesRatioStore


@pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL is not configured; PostgreSQL integration test skipped",
)
def test_real_postgres_derivatives_ratio_round_trip_and_cleanup(tmp_path):
    database_url = os.environ["TEST_DATABASE_URL"]
    symbol = f"RATIO{uuid.uuid4().hex[:10].upper()}"
    timestamp = int(time.time() * 1000) - 60_000
    store = DerivativesRatioStore(str(tmp_path / "unused.sqlite3"), database_url)
    try:
        result = store.save("GLOBAL_LONG_SHORT", symbol, "1h", [{
            "symbol": symbol, "timestamp": timestamp,
            "longShortRatio": "1.25", "longAccount": "0.56", "shortAccount": "0.44",
        }], source="POSTGRES_INTEGRATION_TEST")
        assert result["storage"] == "POSTGRESQL"
        history = store.history("GLOBAL_LONG_SHORT", symbol, "1h")
        assert history["returned_count"] == 1
        assert history["records"][0]["long_short_ratio"] == 1.25
        assert history["source"].startswith("Neon PostgreSQL")
    finally:
        with store._connect_postgres() as connection:
            connection.execute(
                "DELETE FROM public.derivatives_ratio_history WHERE market=%s AND symbol=%s",
                ("USD_M", symbol),
            )
