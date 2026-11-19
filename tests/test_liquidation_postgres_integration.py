"""Opt-in PostgreSQL integration test for liquidation event storage."""
import os
import time
import uuid

import pytest

from app.services.liquidation_collector import LiquidationStore


@pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL is not configured; PostgreSQL integration test skipped",
)
def test_real_postgres_liquidation_event_round_trip_and_cleanup(tmp_path):
    database_url = os.environ["TEST_DATABASE_URL"]
    store = LiquidationStore(str(tmp_path / "unused-liquidations.sqlite3"), database_url)
    symbol = f"TESTLIQ{uuid.uuid4().hex[:12].upper()}"
    event_time = int(time.time() * 1000)
    event = {
        "event_time_ms": event_time, "trade_time_ms": event_time,
        "symbol": symbol, "pair_symbol": None, "market_type": 1,
        "side": "SELL", "order_type": "LIMIT", "status": "FILLED",
        "average_price": 100.0, "original_quantity": 2.0,
        "last_filled_quantity": 2.0, "cumulative_filled_quantity": 2.0,
        "approx_cumulative_notional": 200.0, "raw_json": '{"e":"forceOrder"}',
    }
    try:
        store.insert(event)
        store.insert(event)
        records = store.recent(symbol, 10)
        assert len(records) == 1
        assert records[0]["event_time_ms"] == event_time
        assert records[0]["side"] == "SELL"
        assert records[0]["approx_cumulative_notional"] == 200.0
    finally:
        with store._connect_postgres() as connection:
            connection.execute(
                "DELETE FROM public.liquidation_events WHERE symbol=%s AND event_time_ms=%s",
                (symbol, event_time),
            )
