"""Opt-in PostgreSQL integration test for aggregate trade history."""
import os
import time
import uuid

import pytest

from app.services.aggregate_trade_stream import AggregateTradeStore


@pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL is not configured; PostgreSQL integration test skipped",
)
def test_real_postgres_aggregate_trade_round_trip_and_cleanup(tmp_path):
    database_url = os.environ["TEST_DATABASE_URL"]
    symbol = f"TRD{uuid.uuid4().hex[:10].upper()}"
    trade_id = int(time.time() * 1000)
    store = AggregateTradeStore(str(tmp_path / "unused-trades.sqlite3"), database_url)
    row = {
        "market": "USD_M", "symbol": symbol, "trade_id": trade_id,
        "event_time_ms": trade_id, "trade_time_ms": trade_id,
        "price": 100.0, "quantity": 2.0, "notional": 200.0,
        "buyer_is_maker": False, "aggressor_side": "BUY",
        "raw_json": '{"e":"aggTrade"}',
    }
    try:
        store.insert(row)
        store.insert(row)
        assert store.count("USD_M", symbol) == 1
        records = store.recent("USD_M", symbol, 10)
        assert len(records) == 1
        assert records[0]["buyer_is_maker"] is False
        assert records[0]["aggressor_side"] == "BUY"
    finally:
        with store._connect_postgres() as connection:
            connection.execute(
                "DELETE FROM public.aggregate_trades WHERE market=%s AND symbol=%s",
                ("USD_M", symbol),
            )
