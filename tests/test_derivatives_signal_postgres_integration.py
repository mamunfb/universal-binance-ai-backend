"""Opt-in PostgreSQL integration test for derivatives signal snapshots."""
import os
import time
import uuid

import pytest

from app.services.advanced_derivatives_analysis import DerivativesSignalStore


@pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL is not configured; PostgreSQL integration test skipped",
)
def test_real_postgres_derivatives_signal_snapshot_round_trip_and_cleanup(tmp_path):
    database_url = os.environ["TEST_DATABASE_URL"]
    symbol = f"SIG{uuid.uuid4().hex[:10].upper()}"
    end_time_ms = int(time.time() * 1000) - 60_000
    store = DerivativesSignalStore(str(tmp_path / "unused-signals.sqlite3"), database_url)
    payload = {
        "status": "COMPLETED", "symbol": symbol, "period": "1h",
        "window": {"end_time_ms": end_time_ms}, "analysis": {"bias": "MIXED"},
    }
    try:
        result = store.save(payload)
        assert result["status"] == "STORED"
        assert result["storage"] == "POSTGRESQL"
        history = store.history(symbol, "1h")
        assert history["returned_count"] == 1
        assert history["snapshots"][0]["analysis"]["analysis"]["bias"] == "MIXED"
        assert history["source"].startswith("Neon PostgreSQL")
    finally:
        with store._connect_postgres() as connection:
            connection.execute(
                "DELETE FROM public.derivatives_signal_snapshots WHERE market=%s AND symbol=%s",
                ("USD_M", symbol),
            )
