"""Opt-in real PostgreSQL test for historical OHLCV persistence.

Use only a disposable Neon branch/database with migrations/002_historical_klines.sql applied.
"""
import os
import time
import uuid

import pytest

from app.services.historical_klines import HistoricalKlineStore


@pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL is not configured; PostgreSQL integration test skipped",
)
def test_real_postgres_historical_klines_save_latest_history_and_cleanup(tmp_path):
    store = HistoricalKlineStore(
        str(tmp_path / "unused.sqlite3"),
        os.environ["TEST_DATABASE_URL"],
    )
    symbol = f"TEST{uuid.uuid4().hex[:12].upper()}"
    open_time = int(time.time() * 1000) - 120_000
    row = [
        open_time, "100", "105", "99", "102", "10",
        open_time + 59_999, "1000", 25, "4", "400", "0",
    ]

    try:
        result = store.save_klines("SPOT", symbol, "1m", [row], source="POSTGRES_INTEGRATION_TEST")
        assert result["storage"] == "POSTGRESQL"
        assert store.latest_open_time("SPOT", symbol, "1m") == open_time
        history = store.history("SPOT", symbol, "1m")
        assert history["returned_count"] == 1
        assert history["candles"][0]["open_time_ms"] == open_time
        assert history["candles"][0]["close"] == 102.0
        assert history["source"].startswith("Neon PostgreSQL")
    finally:
        with store._connect_postgres() as connection:
            connection.execute(
                """DELETE FROM public.historical_klines
                   WHERE market=%s AND symbol=%s AND interval=%s AND open_time_ms=%s""",
                ("SPOT", symbol, "1m", open_time),
            )
