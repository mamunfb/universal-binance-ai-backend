"""Verify lease takeover waits for an in-flight, already-fenced PostgreSQL store write."""
import contextvars
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from datetime import datetime, timezone

import pytest

from app.services.collector_leases import (
    ACTIVE_COLLECTOR_LEASE,
    CollectorLeaseContext,
    CollectorLeaseStore,
    assert_current_collector_lease,
)
from app.services.aggregate_trade_stream import AggregateTradeStore
from app.services.funding_rates import FundingRateStore
from app.services.historical_klines import HistoricalKlineStore
from app.services.liquidation_collector import LiquidationStore
from app.services.open_interest import OpenInterestStore
from app.services.order_book_stream import OrderBookHistoryStore


@pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL is not configured; PostgreSQL integration test skipped",
)
@pytest.mark.parametrize(
    "store_kind",
    [
        "liquidation",
        "order_book",
        "aggregate_trades",
        "funding_rates",
        "open_interest",
        "historical_klines",
    ],
)
def test_expired_lease_takeover_waits_for_inflight_fenced_store_write(
    store_kind, tmp_path, monkeypatch
):
    """A write that locked a valid lease row commits before takeover can advance generation."""
    import app.services.aggregate_trade_stream as aggregate_module
    import app.services.funding_rates as funding_module
    import app.services.historical_klines as klines_module
    import app.services.liquidation_collector as liquidation_module
    import app.services.open_interest as oi_module
    import app.services.order_book_stream as order_book_module

    database_url = os.environ["TEST_DATABASE_URL"]
    suffix = uuid.uuid4().hex[:12].upper()
    symbol = f"LOCK{suffix}"
    collector_names = {
        "liquidation": "liquidation:all",
        "order_book": "order-book:all",
        "aggregate_trades": "aggregate-trades:all",
        "funding_rates": "derivatives-history:all",
        "open_interest": "derivatives-history:all",
        "historical_klines": "historical-klines:all",
    }
    modules = {
        "liquidation": liquidation_module,
        "order_book": order_book_module,
        "aggregate_trades": aggregate_module,
        "funding_rates": funding_module,
        "open_interest": oi_module,
        "historical_klines": klines_module,
    }
    collector_name = collector_names[store_kind]
    lease_store = CollectorLeaseStore(database_url)
    old_owner = f"writer-{uuid.uuid4().hex}"
    new_owner = f"takeover-{uuid.uuid4().hex}"
    generation = lease_store.acquire(collector_name, old_owner, 5)
    assert generation == 1

    stores = {
        "liquidation": LiquidationStore(str(tmp_path / "unused.sqlite3"), database_url),
        "order_book": OrderBookHistoryStore(str(tmp_path / "unused.sqlite3"), database_url),
        "aggregate_trades": AggregateTradeStore(str(tmp_path / "unused.sqlite3"), database_url),
        "funding_rates": FundingRateStore(str(tmp_path / "unused.sqlite3"), database_url),
        "open_interest": OpenInterestStore(str(tmp_path / "unused.sqlite3"), database_url),
        "historical_klines": HistoricalKlineStore(str(tmp_path / "unused.sqlite3"), database_url),
    }
    store = stores[store_kind]
    write_has_lease_lock = Event()
    allow_write_to_commit = Event()
    takeover_started = Event()
    context_token = ACTIVE_COLLECTOR_LEASE.set(
        CollectorLeaseContext(collector_name, old_owner, generation)
    )
    original_assert = assert_current_collector_lease

    def pause_after_fence(connection, requested_collector_name):
        original_assert(connection, requested_collector_name)
        write_has_lease_lock.set()
        if not allow_write_to_commit.wait(timeout=15):
            raise TimeoutError("test did not release the in-flight store write")

    monkeypatch.setattr(modules[store_kind], "assert_current_collector_lease", pause_after_fence)
    timestamp_ms = int(time.time() * 1000)

    if store_kind == "liquidation":
        write = lambda: store.insert({
            "event_time_ms": timestamp_ms, "trade_time_ms": timestamp_ms,
            "symbol": symbol, "pair_symbol": None, "market_type": None,
            "side": "BUY", "order_type": "LIMIT", "status": "FILLED",
            "average_price": 100.0, "original_quantity": 1.0,
            "last_filled_quantity": 1.0, "cumulative_filled_quantity": 1.0,
            "approx_cumulative_notional": 100.0, "raw_json": "{}",
        })
    elif store_kind == "order_book":
        write = lambda: store.insert({
            "market": "USD_M", "symbol": symbol, "event_time_ms": timestamp_ms,
            "transaction_time_ms": timestamp_ms, "update_id": timestamp_ms,
            "sampled_at": datetime.now(timezone.utc).isoformat(),
            "best_bid": 100.0, "best_ask": 101.0, "mid_price": 100.5,
            "spread_bps": 99.5, "bid_notional": 100.0, "ask_notional": 101.0,
            "depth_imbalance": 0.0, "bids": [[100.0, 1.0]], "asks": [[101.0, 1.0]],
        })
    elif store_kind == "aggregate_trades":
        write = lambda: store.insert({
            "market": "USD_M", "symbol": symbol, "trade_id": timestamp_ms,
            "event_time_ms": timestamp_ms, "trade_time_ms": timestamp_ms,
            "price": 100.0, "quantity": 1.0, "notional": 100.0,
            "buyer_is_maker": False, "aggressor_side": "BUY", "raw_json": "{}",
        })
    elif store_kind == "funding_rates":
        write = lambda: store.save("USD_M", symbol, [{
            "symbol": symbol, "fundingTime": timestamp_ms,
            "fundingRate": "0.0001", "markPrice": "100",
        }])
    elif store_kind == "open_interest":
        write = lambda: store.save("USD_M", symbol, "1h", [{
            "symbol": symbol, "timestamp": timestamp_ms,
            "sumOpenInterest": "1", "sumOpenInterestValue": "100",
            "CMCCirculatingSupply": None,
        }])
    else:
        write = lambda: store.save_klines(
            "USD_M", symbol, "1m",
            [[timestamp_ms, "100", "101", "99", "100.5", "1",
              timestamp_ms + 59_999, "100", 1, "0.5", "50"]],
            observation_started_at_ns=time.time_ns(),
        )

    writer_context = contextvars.copy_context()

    def run_old_writer():
        return writer_context.run(write)

    def attempt_takeover():
        takeover_started.set()
        return lease_store.acquire(collector_name, new_owner, 30)

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            writer = pool.submit(run_old_writer)
            assert write_has_lease_lock.wait(timeout=5)

            # Let the original lease expire while the fenced write holds FOR SHARE.
            time.sleep(5.2)
            takeover = pool.submit(attempt_takeover)
            assert takeover_started.wait(timeout=2)
            time.sleep(0.25)
            assert takeover.done() is False, "takeover bypassed an in-flight fenced write"

            allow_write_to_commit.set()
            writer.result(timeout=5)
            new_generation = takeover.result(timeout=5)

        assert new_generation == generation + 1
    finally:
        allow_write_to_commit.set()
        ACTIVE_COLLECTOR_LEASE.reset(context_token)
        with lease_store._connect() as connection:
            cleanup = {
                "liquidation": "DELETE FROM public.liquidation_events WHERE symbol = %s",
                "order_book": "DELETE FROM public.order_book_samples WHERE market = 'USD_M' AND symbol = %s",
                "aggregate_trades": "DELETE FROM public.aggregate_trades WHERE market = 'USD_M' AND symbol = %s",
                "funding_rates": "DELETE FROM public.historical_funding_rates WHERE market = 'USD_M' AND symbol = %s",
                "open_interest": "DELETE FROM public.historical_open_interest WHERE market = 'USD_M' AND symbol = %s",
                "historical_klines": "DELETE FROM public.historical_klines WHERE market = 'USD_M' AND symbol = %s",
            }
            connection.execute(cleanup[store_kind], (symbol,))
            connection.execute(
                "DELETE FROM public.collector_leases WHERE collector_name = %s",
                (collector_name,),
            )
