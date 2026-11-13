"""PostgreSQL integration coverage for stale collector leases at every write boundary."""
import os
import time
import uuid
from datetime import datetime, timezone

import pytest

from app.services.aggregate_trade_stream import AggregateTradeStore
from app.services.collector_leases import (
    ACTIVE_COLLECTOR_LEASE,
    CollectorLeaseContext,
    CollectorLeaseLostError,
    CollectorLeaseStore,
)
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
def test_stale_generation_rejected_at_every_scheduled_store_write_boundary(
    store_kind, tmp_path
):
    """A previous owner must not write after a real PostgreSQL lease takeover."""
    database_url = os.environ["TEST_DATABASE_URL"]
    suffix = uuid.uuid4().hex[:12].upper()
    symbol = f"FENCE{suffix}"
    collector_names = {
        "liquidation": "liquidation:all",
        "order_book": "order-book:all",
        "aggregate_trades": "aggregate-trades:all",
        "funding_rates": "derivatives-history:all",
        "open_interest": "derivatives-history:all",
        "historical_klines": "historical-klines:all",
    }
    collector_name = collector_names[store_kind]
    old_owner = f"old-{uuid.uuid4().hex}"
    new_owner = f"new-{uuid.uuid4().hex}"
    lease_store = CollectorLeaseStore(database_url)
    old_context_token = None
    timestamp_ms = int(time.time() * 1000)

    stores = {
        "liquidation": LiquidationStore(str(tmp_path / "unused.sqlite3"), database_url),
        "order_book": OrderBookHistoryStore(str(tmp_path / "unused.sqlite3"), database_url),
        "aggregate_trades": AggregateTradeStore(str(tmp_path / "unused.sqlite3"), database_url),
        "funding_rates": FundingRateStore(str(tmp_path / "unused.sqlite3"), database_url),
        "open_interest": OpenInterestStore(str(tmp_path / "unused.sqlite3"), database_url),
        "historical_klines": HistoricalKlineStore(str(tmp_path / "unused.sqlite3"), database_url),
    }
    store = stores[store_kind]

    try:
        old_generation = lease_store.acquire(collector_name, old_owner, 30)
        assert old_generation == 1

        # Expire the first owner and let a second owner take generation 2.
        with lease_store._connect() as connection:
            connection.execute(
                """
                UPDATE public.collector_leases
                SET lease_expires_at = clock_timestamp() - INTERVAL '1 second'
                WHERE collector_name = %s
                """,
                (collector_name,),
            )
        new_generation = lease_store.acquire(collector_name, new_owner, 30)
        assert new_generation == old_generation + 1

        # Simulate a delayed worker resuming with the old, now-stale context.
        old_context_token = ACTIVE_COLLECTOR_LEASE.set(
            CollectorLeaseContext(collector_name, old_owner, old_generation)
        )

        if store_kind == "liquidation":
            write = lambda: store.insert({
                "event_time_ms": timestamp_ms,
                "trade_time_ms": timestamp_ms,
                "symbol": symbol,
                "pair_symbol": None,
                "market_type": None,
                "side": "BUY",
                "order_type": "LIMIT",
                "status": "FILLED",
                "average_price": 100.0,
                "original_quantity": 1.0,
                "last_filled_quantity": 1.0,
                "cumulative_filled_quantity": 1.0,
                "approx_cumulative_notional": 100.0,
                "raw_json": "{}",
            })
        elif store_kind == "order_book":
            write = lambda: store.insert({
                "market": "USD_M",
                "symbol": symbol,
                "event_time_ms": timestamp_ms,
                "transaction_time_ms": timestamp_ms,
                "update_id": timestamp_ms,
                "sampled_at": datetime.now(timezone.utc).isoformat(),
                "best_bid": 100.0,
                "best_ask": 101.0,
                "mid_price": 100.5,
                "spread_bps": 99.5,
                "bid_notional": 100.0,
                "ask_notional": 101.0,
                "depth_imbalance": 0.0,
                "bids": [[100.0, 1.0]],
                "asks": [[101.0, 1.0]],
            })
        elif store_kind == "aggregate_trades":
            write = lambda: store.insert({
                "market": "USD_M",
                "symbol": symbol,
                "trade_id": timestamp_ms,
                "event_time_ms": timestamp_ms,
                "trade_time_ms": timestamp_ms,
                "price": 100.0,
                "quantity": 1.0,
                "notional": 100.0,
                "buyer_is_maker": False,
                "aggressor_side": "BUY",
                "raw_json": "{}",
            })
        elif store_kind == "funding_rates":
            write = lambda: store.save("USD_M", symbol, [{
                "symbol": symbol,
                "fundingTime": timestamp_ms,
                "fundingRate": "0.0001",
                "markPrice": "100",
            }])
        elif store_kind == "open_interest":
            write = lambda: store.save("USD_M", symbol, "1h", [{
                "symbol": symbol,
                "timestamp": timestamp_ms,
                "sumOpenInterest": "1",
                "sumOpenInterestValue": "100",
                "CMCCirculatingSupply": None,
            }])
        else:
            write = lambda: store.save_klines(
                "USD_M",
                symbol,
                "1m",
                [[timestamp_ms, "100", "101", "99", "100.5", "1",
                  timestamp_ms + 59_999, "100", 1, "0.5", "50"]],
                observation_started_at_ns=time.time_ns(),
            )

        with pytest.raises(CollectorLeaseLostError):
            write()
    finally:
        if old_context_token is not None:
            ACTIVE_COLLECTOR_LEASE.reset(old_context_token)

        # Clean up defensively if a regression ever lets a stale write through.
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
