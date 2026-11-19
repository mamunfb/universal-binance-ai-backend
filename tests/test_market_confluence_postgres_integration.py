"""Opt-in real PostgreSQL integration test.

Set TEST_DATABASE_URL to a disposable Neon branch/database with migrations applied.
The test inserts one uniquely keyed row and removes it in a finally block.
"""
import os
import time
import uuid

import pytest

from app.services.market_confluence_store import MarketConfluenceStore


@pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL is not configured; real PostgreSQL integration test skipped",
)
def test_real_postgres_snapshot_insert_read_and_cleanup(tmp_path):
    database_url = os.environ["TEST_DATABASE_URL"]
    store = MarketConfluenceStore(str(tmp_path / "unused.sqlite3"), database_url)
    symbol = f"TEST{uuid.uuid4().hex[:12].upper()}"
    analyzed_at_ms = int(time.time() * 1000)
    payload = {
        "market": "SPOT",
        "symbol": symbol,
        "interval": "1m",
        "analyzed_at_ms": analyzed_at_ms,
        "confluence": {"bias": "UNKNOWN", "alignment": "INTEGRATION_TEST"},
        "reference": {},
        "evidence": [{"source": "AUTOMATED_POSTGRES_INTEGRATION_TEST"}],
    }

    try:
        saved = store.save(payload)
        snapshot = store.get_snapshot("SPOT", symbol, saved["snapshot_id"])
        history = store.history("SPOT", symbol, "1m", limit=5)

        assert saved["status"] == "STORED"
        assert snapshot is not None
        assert snapshot["payload"] == payload
        assert history["returned_count"] == 1
        assert history["snapshots"][0]["snapshot_id"] == saved["snapshot_id"]
    finally:
        with store._connect_postgres() as db:
            db.execute(
                """DELETE FROM public.market_confluence_snapshots
                WHERE market=%s AND symbol=%s AND interval=%s AND analyzed_at_ms=%s""",
                ("SPOT", symbol, "1m", analyzed_at_ms),
            )
