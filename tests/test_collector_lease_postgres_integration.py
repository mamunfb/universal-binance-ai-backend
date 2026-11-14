"""Real PostgreSQL tests for collector lease/fencing primitives.

The CI workflow supplies TEST_DATABASE_URL and applies all SQL migrations first.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError

import psycopg
import pytest

from app.services.collector_lease import CollectorLeaseLostError, PostgresCollectorLease
from app.services.funding_rates import FundingRateStore
from app.services.historical_klines import HistoricalKlineStore
from app.services.open_interest import OpenInterestStore
from app.services.order_book_stream import OrderBookHistoryStore
from app.services.aggregate_trade_stream import AggregateTradeStore
from app.services.liquidation_collector import LiquidationStore, normalize_force_order


requires_postgres = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL is not configured; PostgreSQL lease integration test skipped",
)


def _lease(name: str, ttl: int = 30) -> PostgresCollectorLease:
    return PostgresCollectorLease(os.environ["TEST_DATABASE_URL"], name, ttl_seconds=ttl)


@requires_postgres
def test_two_independent_owners_cannot_acquire_the_same_live_lease():
    name = f"lease-test-{uuid.uuid4().hex}"
    first, second = _lease(name), _lease(name)

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda item: item.acquire(), (first, second)))
        assert sum(result is not None for result in results) == 1
        winner = first if results[0] is not None else second
        winner_lease = results[0] if winner is first else results[1]
        loser = second if winner is first else first
        assert loser.acquire() is None
        assert winner.release(winner_lease) is True
    finally:
        with psycopg.connect(os.environ["TEST_DATABASE_URL"]) as connection:
            connection.execute("DELETE FROM public.collector_leases WHERE lease_name = %s", (name,))


@requires_postgres
def test_expired_lease_takeover_increments_fencing_token_and_rejects_stale_owner():
    name = f"lease-test-{uuid.uuid4().hex}"
    first, second = _lease(name), _lease(name)
    try:
        old_lease = first.acquire()
        assert old_lease is not None
        with psycopg.connect(os.environ["TEST_DATABASE_URL"]) as connection:
            connection.execute(
                "UPDATE public.collector_leases SET lease_expires_at = clock_timestamp() - INTERVAL '1 second' WHERE lease_name = %s",
                (name,),
            )

        new_lease = second.acquire()
        assert new_lease is not None
        assert new_lease.fencing_token == old_lease.fencing_token + 1
        assert first.renew(old_lease) is None
        assert first.release(old_lease) is False

        with psycopg.connect(os.environ["TEST_DATABASE_URL"]) as connection:
            assert PostgresCollectorLease.lock_if_owned(connection, old_lease) is False
            assert PostgresCollectorLease.lock_if_owned(connection, new_lease) is True
    finally:
        with psycopg.connect(os.environ["TEST_DATABASE_URL"]) as connection:
            connection.execute("DELETE FROM public.collector_leases WHERE lease_name = %s", (name,))


@requires_postgres
def test_renewal_preserves_token_and_release_does_not_delete_fencing_history():
    name = f"lease-test-{uuid.uuid4().hex}"
    owner = _lease(name)
    successor = _lease(name)
    try:
        lease = owner.acquire()
        assert lease is not None
        renewed = owner.renew(lease)
        assert renewed is not None
        assert renewed.fencing_token == lease.fencing_token
        assert owner.release(renewed) is True
        next_lease = successor.acquire()
        assert next_lease is not None
        assert next_lease.fencing_token == lease.fencing_token + 1
    finally:
        with psycopg.connect(os.environ["TEST_DATABASE_URL"]) as connection:
            connection.execute("DELETE FROM public.collector_leases WHERE lease_name = %s", (name,))


def test_lease_configuration_rejects_invalid_values():
    database_url = os.getenv("TEST_DATABASE_URL", "postgresql://localhost/test")
    for name, ttl in (("", 30), ("valid", 4), ("valid", 3601), ("valid", True)):
        with pytest.raises(ValueError):
            PostgresCollectorLease(database_url, name, ttl_seconds=ttl)


def test_lease_configuration_rejects_invalid_explicit_owner_id():
    database_url = os.getenv("TEST_DATABASE_URL", "postgresql://localhost/test")
    for owner_id in ("", 123):
        with pytest.raises(ValueError):
            PostgresCollectorLease(database_url, "valid-name", owner_id=owner_id)


@requires_postgres
def test_live_fenced_write_transaction_blocks_expired_lease_takeover():
    """A new owner cannot advance the token while an old owner's fenced write is open."""
    name = f"lease-test-{uuid.uuid4().hex}"
    first, second = _lease(name, ttl=5), _lease(name, ttl=5)
    try:
        old_lease = first.acquire()
        assert old_lease is not None

        with ThreadPoolExecutor(max_workers=1) as pool:
            with psycopg.connect(os.environ["TEST_DATABASE_URL"]) as connection:
                assert PostgresCollectorLease.lock_if_owned(connection, old_lease) is True
                # Let the lease expire while its validated write transaction retains FOR SHARE.
                time.sleep(5.1)
                takeover = pool.submit(second.acquire)
                with pytest.raises(TimeoutError):
                    takeover.result(timeout=0.2)

            # Once the fenced transaction commits, the expired lease can be taken over.
            new_lease = takeover.result(timeout=5)
        assert new_lease is not None
        assert new_lease.fencing_token == old_lease.fencing_token + 1
    finally:
        with psycopg.connect(os.environ["TEST_DATABASE_URL"]) as connection:
            connection.execute("DELETE FROM public.collector_leases WHERE lease_name = %s", (name,))



@requires_postgres
def test_historical_kline_store_rejects_stale_lease_and_accepts_current_owner():
    name = f"lease-test-{uuid.uuid4().hex}"
    symbol = f"LEASE{uuid.uuid4().hex[:8].upper()}"
    first, second = _lease(name), _lease(name)
    store = HistoricalKlineStore(":unused:", database_url=os.environ["TEST_DATABASE_URL"])
    candle = [
        1_700_000_040_000, "100", "105", "99", "101", "10",
        1_700_000_099_999, "1000", 25, "4", "400", "0",
    ]
    try:
        old_lease = first.acquire()
        assert old_lease is not None
        saved = store.save_klines("SPOT", symbol, "1m", [candle], lease=old_lease)
        assert saved["stored_count"] == 1

        with psycopg.connect(os.environ["TEST_DATABASE_URL"]) as connection:
            connection.execute(
                "UPDATE public.collector_leases SET lease_expires_at = clock_timestamp() - INTERVAL '1 second' WHERE lease_name = %s",
                (name,),
            )
        current_lease = second.acquire()
        assert current_lease is not None
        assert current_lease.fencing_token == old_lease.fencing_token + 1

        stale_candle = [*candle]
        stale_candle[0] += 60_000
        stale_candle[6] += 60_000
        with pytest.raises(CollectorLeaseLostError):
            store.save_klines("SPOT", symbol, "1m", [stale_candle], lease=old_lease)

        accepted_candle = [*candle]
        accepted_candle[0] += 120_000
        accepted_candle[6] += 120_000
        accepted = store.save_klines(
            "SPOT", symbol, "1m", [accepted_candle], lease=current_lease
        )
        assert accepted["stored_count"] == 1
        history = store.history("SPOT", symbol, "1m")
        assert history["returned_count"] == 2
    finally:
        with psycopg.connect(os.environ["TEST_DATABASE_URL"]) as connection:
            connection.execute(
                "DELETE FROM public.historical_klines WHERE market = 'SPOT' AND symbol = %s",
                (symbol,),
            )
            connection.execute("DELETE FROM public.collector_leases WHERE lease_name = %s", (name,))



@requires_postgres
def test_funding_rate_store_rejects_stale_lease_and_accepts_current_owner():
    name = f"lease-test-{uuid.uuid4().hex}"
    symbol = f"FUND{uuid.uuid4().hex[:8].upper()}"
    first, second = _lease(name), _lease(name)
    store = FundingRateStore(":unused:", database_url=os.environ["TEST_DATABASE_URL"])
    event = {
        "symbol": symbol, "fundingTime": 1_700_000_040_000,
        "fundingRate": "0.0001", "markPrice": "37000",
    }
    try:
        old_lease = first.acquire()
        assert old_lease is not None
        store.save("USD_M", symbol, [event], lease=old_lease)
        with psycopg.connect(os.environ["TEST_DATABASE_URL"]) as connection:
            connection.execute(
                "UPDATE public.collector_leases SET lease_expires_at = clock_timestamp() - INTERVAL '1 second' WHERE lease_name = %s",
                (name,),
            )
        current_lease = second.acquire()
        assert current_lease is not None
        stale_event = {**event, "fundingTime": event["fundingTime"] + 8 * 60 * 60 * 1000}
        with pytest.raises(CollectorLeaseLostError):
            store.save("USD_M", symbol, [stale_event], lease=old_lease)
        accepted_event = {**event, "fundingTime": event["fundingTime"] + 16 * 60 * 60 * 1000}
        result = store.save("USD_M", symbol, [accepted_event], lease=current_lease)
        assert result["stored_count"] == 1
        assert store.history("USD_M", symbol)["returned_count"] == 2
    finally:
        with psycopg.connect(os.environ["TEST_DATABASE_URL"]) as connection:
            connection.execute(
                "DELETE FROM public.historical_funding_rates WHERE symbol = %s", (symbol,)
            )
            connection.execute("DELETE FROM public.collector_leases WHERE lease_name = %s", (name,))


@requires_postgres
def test_open_interest_store_rejects_stale_lease_and_accepts_current_owner():
    name = f"lease-test-{uuid.uuid4().hex}"
    symbol = f"OPEN{uuid.uuid4().hex[:8].upper()}"
    first, second = _lease(name), _lease(name)
    store = OpenInterestStore(":unused:", database_url=os.environ["TEST_DATABASE_URL"])
    record = {
        "symbol": symbol, "timestamp": 1_700_000_040_000,
        "sumOpenInterest": "10", "sumOpenInterestValue": "1000",
    }
    try:
        old_lease = first.acquire()
        assert old_lease is not None
        store.save("USD_M", symbol, "1h", [record], lease=old_lease)
        with psycopg.connect(os.environ["TEST_DATABASE_URL"]) as connection:
            connection.execute(
                "UPDATE public.collector_leases SET lease_expires_at = clock_timestamp() - INTERVAL '1 second' WHERE lease_name = %s",
                (name,),
            )
        current_lease = second.acquire()
        assert current_lease is not None
        stale_record = {**record, "timestamp": record["timestamp"] + 60 * 60 * 1000}
        with pytest.raises(CollectorLeaseLostError):
            store.save("USD_M", symbol, "1h", [stale_record], lease=old_lease)
        accepted_record = {**record, "timestamp": record["timestamp"] + 2 * 60 * 60 * 1000}
        result = store.save("USD_M", symbol, "1h", [accepted_record], lease=current_lease)
        assert result["stored_count"] == 1
        assert store.history("USD_M", symbol, "1h")["returned_count"] == 2
    finally:
        with psycopg.connect(os.environ["TEST_DATABASE_URL"]) as connection:
            connection.execute(
                "DELETE FROM public.historical_open_interest WHERE symbol = %s", (symbol,)
            )
            connection.execute("DELETE FROM public.collector_leases WHERE lease_name = %s", (name,))



@requires_postgres
def test_order_book_store_rejects_stale_lease_and_accepts_current_owner():
    name = f"lease-test-{uuid.uuid4().hex}"
    symbol = f"BOOK{uuid.uuid4().hex[:8].upper()}"
    first, second = _lease(name), _lease(name)
    store = OrderBookHistoryStore(":unused:", database_url=os.environ["TEST_DATABASE_URL"])

    def sample(update_id):
        return {
            "market": "SPOT", "symbol": symbol, "event_time_ms": 1_700_000_000_000,
            "transaction_time_ms": 1_700_000_000_000, "update_id": update_id,
            "sampled_at": "2026-11-14T00:00:00+00:00", "best_bid": 100.0,
            "best_ask": 101.0, "mid_price": 100.5, "spread_bps": 99.5,
            "bid_notional": 100.0, "ask_notional": 101.0,
            "depth_imbalance": -0.004975, "bids": [[100.0, 1.0]],
            "asks": [[101.0, 1.0]],
        }

    try:
        old_lease = first.acquire()
        assert old_lease is not None
        store.insert(sample(100), lease=old_lease)
        with psycopg.connect(os.environ["TEST_DATABASE_URL"]) as connection:
            connection.execute(
                "UPDATE public.collector_leases SET lease_expires_at = clock_timestamp() - INTERVAL '1 second' WHERE lease_name = %s",
                (name,),
            )
        current_lease = second.acquire()
        assert current_lease is not None
        with pytest.raises(CollectorLeaseLostError):
            store.insert(sample(101), lease=old_lease)
        store.insert(sample(102), lease=current_lease)
        assert store.count("SPOT", symbol) == 2
    finally:
        with psycopg.connect(os.environ["TEST_DATABASE_URL"]) as connection:
            connection.execute(
                "DELETE FROM public.order_book_samples WHERE market='SPOT' AND symbol=%s",
                (symbol,),
            )
            connection.execute("DELETE FROM public.collector_leases WHERE lease_name = %s", (name,))


@requires_postgres
def test_aggregate_trade_store_rejects_stale_lease_and_accepts_current_owner():
    name = f"lease-test-{uuid.uuid4().hex}"
    symbol = f"AGG{uuid.uuid4().hex[:8].upper()}"
    first, second = _lease(name), _lease(name)
    store = AggregateTradeStore(":unused:", database_url=os.environ["TEST_DATABASE_URL"])

    def trade(trade_id):
        return {
            "market": "SPOT", "symbol": symbol, "trade_id": trade_id,
            "event_time_ms": 1_700_000_000_000, "trade_time_ms": 1_700_000_000_000,
            "price": 100.0, "quantity": 1.0, "notional": 100.0,
            "buyer_is_maker": False, "aggressor_side": "BUY",
            "raw_json": json.dumps({"a": trade_id, "s": symbol}),
        }

    try:
        old_lease = first.acquire()
        assert old_lease is not None
        store.insert(trade(100), lease=old_lease)
        with psycopg.connect(os.environ["TEST_DATABASE_URL"]) as connection:
            connection.execute(
                "UPDATE public.collector_leases SET lease_expires_at = clock_timestamp() - INTERVAL '1 second' WHERE lease_name = %s",
                (name,),
            )
        current_lease = second.acquire()
        assert current_lease is not None
        with pytest.raises(CollectorLeaseLostError):
            store.insert(trade(101), lease=old_lease)
        store.insert(trade(102), lease=current_lease)
        assert store.count("SPOT", symbol) == 2
    finally:
        with psycopg.connect(os.environ["TEST_DATABASE_URL"]) as connection:
            connection.execute(
                "DELETE FROM public.aggregate_trades WHERE market='SPOT' AND symbol=%s",
                (symbol,),
            )
            connection.execute("DELETE FROM public.collector_leases WHERE lease_name = %s", (name,))


@requires_postgres
def test_liquidation_store_rejects_stale_lease_and_accepts_current_owner():
    name = f"lease-test-{uuid.uuid4().hex}"
    symbol = f"LIQ{uuid.uuid4().hex[:8].upper()}"
    first, second = _lease(name), _lease(name)
    store = LiquidationStore(":unused:", database_url=os.environ["TEST_DATABASE_URL"])

    def event(event_time):
        message = {
            "e": "forceOrder", "E": event_time, "st": 1,
            "o": {
                "s": symbol, "ps": symbol, "S": "SELL", "o": "LIMIT",
                "q": "0.02", "p": "50000", "ap": "49900", "X": "FILLED",
                "l": "0.02", "z": "0.02", "T": event_time - 23,
            },
        }
        normalized = normalize_force_order(message)
        assert normalized is not None
        return normalized

    try:
        old_lease = first.acquire()
        assert old_lease is not None
        store.insert(event(1_700_000_000_000), lease=old_lease)
        with psycopg.connect(os.environ["TEST_DATABASE_URL"]) as connection:
            connection.execute(
                "UPDATE public.collector_leases SET lease_expires_at = clock_timestamp() - INTERVAL '1 second' WHERE lease_name = %s",
                (name,),
            )
        current_lease = second.acquire()
        assert current_lease is not None
        with pytest.raises(CollectorLeaseLostError):
            store.insert(event(1_700_000_000_100), lease=old_lease)
        store.insert(event(1_700_000_000_200), lease=current_lease)
        assert len(store.recent(symbol, 10)) == 2
    finally:
        with psycopg.connect(os.environ["TEST_DATABASE_URL"]) as connection:
            connection.execute(
                "DELETE FROM public.liquidation_events WHERE symbol = %s", (symbol,)
            )
            connection.execute("DELETE FROM public.collector_leases WHERE lease_name = %s", (name,))
