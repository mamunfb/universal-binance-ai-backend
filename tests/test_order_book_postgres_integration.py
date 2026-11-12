"""Opt-in PostgreSQL integration test for order-book snapshots."""
import os
import time
import uuid

import pytest

from app.services.order_book_stream import OrderBookHistoryStore


@pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL is not configured; PostgreSQL integration test skipped",
)
def test_real_postgres_order_book_round_trip_and_cleanup(tmp_path):
    database_url = os.environ["TEST_DATABASE_URL"]
    symbol = f"BOOK{uuid.uuid4().hex[:10].upper()}"
    update_id = int(time.time() * 1000)
    store = OrderBookHistoryStore(str(tmp_path / "unused-book.sqlite3"), database_url)
    row = {
        "market": "USD_M", "symbol": symbol, "event_time_ms": update_id,
        "transaction_time_ms": update_id, "update_id": update_id,
        "sampled_at": "2026-01-01T00:00:00+00:00",
        "best_bid": 99.0, "best_ask": 101.0, "mid_price": 100.0,
        "spread_bps": 200.0, "bid_notional": 990.0, "ask_notional": 101.0,
        "depth_imbalance": 0.8, "bids": [[99.0, 10.0]], "asks": [[101.0, 1.0]],
    }
    try:
        store.insert(row)
        store.insert(row)
        assert store.count("USD_M", symbol) == 1
        records = store.recent("USD_M", symbol, 10)
        assert len(records) == 1
        assert records[0]["bids"] == [[99.0, 10.0]]
        assert records[0]["asks"] == [[101.0, 1.0]]
    finally:
        with store._connect_postgres() as connection:
            connection.execute(
                "DELETE FROM public.order_book_samples WHERE market=%s AND symbol=%s",
                ("USD_M", symbol),
            )
