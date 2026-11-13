from __future__ import annotations

import asyncio
import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.services.collector_leases import (
    ACTIVE_COLLECTOR_LEASE,
    CollectorLeaseContext,
    CollectorLeaseCoordinator,
    CollectorLeaseLostError,
    CollectorLeaseStore,
    assert_current_collector_lease,
)


def test_collector_lease_store_allows_only_one_concurrent_owner():
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is not configured")

    store = CollectorLeaseStore(database_url)
    collector_name = f"test-concurrent-{uuid.uuid4().hex}"
    owners = [f"owner-{uuid.uuid4().hex}", f"owner-{uuid.uuid4().hex}"]
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            generations = list(pool.map(
                lambda owner: store.acquire(collector_name, owner, 30), owners
            ))
        assert sum(generation is not None for generation in generations) == 1
        winner_index = next(i for i, generation in enumerate(generations) if generation is not None)
        loser_index = 1 - winner_index
        winner, loser = owners[winner_index], owners[loser_index]
        winner_generation = generations[winner_index]
        assert winner_generation == 1
        assert store.renew(collector_name, winner, winner_generation, 30) is True
        assert store.renew(collector_name, loser, winner_generation, 30) is False
        assert store.release(collector_name, loser, winner_generation) is False
        assert store.release(collector_name, winner, winner_generation) is True
        next_generation = store.acquire(collector_name, loser, 30)
        assert next_generation == 2
        assert store.release(collector_name, loser, next_generation) is True
    finally:
        with store._connect() as connection:
            connection.execute(
                "DELETE FROM public.collector_leases WHERE collector_name=%s",
                (collector_name,),
            )


def test_collector_lease_expired_owner_can_be_replaced():
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is not configured")

    store = CollectorLeaseStore(database_url)
    collector_name = f"test-expiry-{uuid.uuid4().hex}"
    first_owner = f"owner-{uuid.uuid4().hex}"
    next_owner = f"owner-{uuid.uuid4().hex}"
    try:
        first_generation = store.acquire(collector_name, first_owner, 30)
        assert first_generation == 1
        with store._connect() as connection:
            connection.execute(
                """
                UPDATE public.collector_leases
                SET lease_expires_at = NOW() - INTERVAL '1 second'
                WHERE collector_name=%s
                """,
                (collector_name,),
            )
        assert store.renew(collector_name, first_owner, first_generation, 30) is False
        next_generation = store.acquire(collector_name, next_owner, 30)
        assert next_generation == first_generation + 1
        assert store.release(collector_name, first_owner, first_generation) is False
        assert store.release(collector_name, next_owner, next_generation) is True
    finally:
        with store._connect() as connection:
            connection.execute(
                "DELETE FROM public.collector_leases WHERE collector_name=%s",
                (collector_name,),
            )


@pytest.mark.asyncio
async def test_lease_coordinator_starts_and_stops_collector_with_owned_lease():
    class FakeLeaseStore:
        def __init__(self):
            self.released = False

        def acquire(self, *_args):
            return 7

        def renew(self, *_args):
            return True

        def release(self, *_args):
            self.released = True
            return True

    started = asyncio.Event()
    stopped = asyncio.Event()
    observed_lease = {}
    store = FakeLeaseStore()

    def start_collector():
        observed_lease["context"] = ACTIVE_COLLECTOR_LEASE.get()
        started.set()

    async def stop_collector():
        stopped.set()

    coordinator = CollectorLeaseCoordinator(
        store, "test-collector", start_collector, stop_collector,
        owner_token="owner-1", ttl_seconds=5, heartbeat_seconds=1,
        retry_seconds=1,
    )
    coordinator.start()
    await asyncio.wait_for(started.wait(), timeout=1)
    assert coordinator.status()["state"] == "ACTIVE"
    assert observed_lease["context"] == CollectorLeaseContext("test-collector", "owner-1", 7)
    await coordinator.stop()
    await asyncio.wait_for(stopped.wait(), timeout=1)

    assert store.released is True
    assert coordinator.status()["state"] == "STOPPED"
    assert coordinator.status()["lease_owned"] is False


@pytest.mark.asyncio
async def test_lease_coordinator_stops_collector_when_lease_renewal_is_rejected():
    class FakeLeaseStore:
        def acquire(self, *_args):
            return 8

        def renew(self, *_args):
            return False

        def release(self, *_args):
            return True

    started = asyncio.Event()
    stopped = asyncio.Event()

    def start_collector():
        started.set()

    async def stop_collector():
        stopped.set()

    coordinator = CollectorLeaseCoordinator(
        FakeLeaseStore(), "test-lost-lease", start_collector, stop_collector,
        owner_token="owner-2", ttl_seconds=5, heartbeat_seconds=1,
        retry_seconds=1,
    )
    coordinator.start()
    await asyncio.wait_for(started.wait(), timeout=1)
    await asyncio.wait_for(stopped.wait(), timeout=2)
    await coordinator.stop()

    assert coordinator.status()["state"] == "LEASE_LOST"
    assert coordinator.status()["lease_owned"] is False


def test_fencing_context_rejects_old_owner_after_takeover():
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is not configured")

    store = CollectorLeaseStore(database_url)
    collector_name = f"test-fence-{uuid.uuid4().hex}"
    first_owner = f"owner-{uuid.uuid4().hex}"
    next_owner = f"owner-{uuid.uuid4().hex}"
    first_context_token = None
    try:
        first_generation = store.acquire(collector_name, first_owner, 30)
        assert first_generation == 1
        first_context_token = ACTIVE_COLLECTOR_LEASE.set(
            CollectorLeaseContext(collector_name, first_owner, first_generation)
        )
        with store._connect() as connection:
            assert_current_collector_lease(connection, collector_name)
        ACTIVE_COLLECTOR_LEASE.reset(first_context_token)
        first_context_token = None

        with store._connect() as connection:
            connection.execute(
                """
                UPDATE public.collector_leases
                SET lease_expires_at = NOW() - INTERVAL '1 second'
                WHERE collector_name=%s
                """,
                (collector_name,),
            )
        next_generation = store.acquire(collector_name, next_owner, 30)
        assert next_generation == first_generation + 1

        first_context_token = ACTIVE_COLLECTOR_LEASE.set(
            CollectorLeaseContext(collector_name, first_owner, first_generation)
        )
        with store._connect() as connection:
            with pytest.raises(CollectorLeaseLostError):
                assert_current_collector_lease(connection, collector_name)
        ACTIVE_COLLECTOR_LEASE.reset(first_context_token)
        first_context_token = None

        first_context_token = ACTIVE_COLLECTOR_LEASE.set(
            CollectorLeaseContext(collector_name, next_owner, next_generation)
        )
        with store._connect() as connection:
            assert_current_collector_lease(connection, collector_name)
    finally:
        if first_context_token is not None:
            ACTIVE_COLLECTOR_LEASE.reset(first_context_token)
        with store._connect() as connection:
            connection.execute(
                "DELETE FROM public.collector_leases WHERE collector_name=%s",
                (collector_name,),
            )


def test_stale_lease_generation_cannot_write_aggregate_trade():
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is not configured")

    from app.services.aggregate_trade_stream import AggregateTradeStore

    lease_store = CollectorLeaseStore(database_url)
    trade_store = AggregateTradeStore("unused.sqlite3", database_url)
    collector_name = "aggregate-trades:all"
    symbol = f"FENCE{uuid.uuid4().hex[:12].upper()}"
    first_owner = f"owner-{uuid.uuid4().hex}"
    next_owner = f"owner-{uuid.uuid4().hex}"
    context_token = None
    try:
        # The CI PostgreSQL database is ephemeral; clear a leftover row from an
        # interrupted test run before claiming this collector's production key.
        with lease_store._connect() as connection:
            connection.execute(
                "DELETE FROM public.collector_leases WHERE collector_name=%s",
                (collector_name,),
            )
        first_generation = lease_store.acquire(collector_name, first_owner, 30)
        assert first_generation is not None
        context_token = ACTIVE_COLLECTOR_LEASE.set(
            CollectorLeaseContext(collector_name, first_owner, first_generation)
        )
        trade_store.insert({
            "market": "SPOT", "symbol": symbol, "trade_id": 900001,
            "event_time_ms": 1_700_000_000_000, "trade_time_ms": 1_700_000_000_000,
            "price": 1.0, "quantity": 1.0, "notional": 1.0,
            "buyer_is_maker": False, "aggressor_side": "BUY", "raw_json": "{}",
        })
        ACTIVE_COLLECTOR_LEASE.reset(context_token)
        context_token = None

        with lease_store._connect() as connection:
            connection.execute(
                """
                UPDATE public.collector_leases
                SET lease_expires_at = NOW() - INTERVAL '1 second'
                WHERE collector_name=%s
                """,
                (collector_name,),
            )
        next_generation = lease_store.acquire(collector_name, next_owner, 30)
        assert next_generation == first_generation + 1

        context_token = ACTIVE_COLLECTOR_LEASE.set(
            CollectorLeaseContext(collector_name, first_owner, first_generation)
        )
        with pytest.raises(CollectorLeaseLostError):
            trade_store.insert({
                "market": "SPOT", "symbol": symbol, "trade_id": 900002,
                "event_time_ms": 1_700_000_000_001, "trade_time_ms": 1_700_000_000_001,
                "price": 1.0, "quantity": 1.0, "notional": 1.0,
                "buyer_is_maker": False, "aggressor_side": "BUY", "raw_json": "{}",
            })
        ACTIVE_COLLECTOR_LEASE.reset(context_token)
        context_token = None

        assert [row["trade_id"] for row in trade_store.recent("SPOT", symbol)] == [900001]
        context_token = ACTIVE_COLLECTOR_LEASE.set(
            CollectorLeaseContext(collector_name, next_owner, next_generation)
        )
        trade_store.insert({
            "market": "SPOT", "symbol": symbol, "trade_id": 900003,
            "event_time_ms": 1_700_000_000_002, "trade_time_ms": 1_700_000_000_002,
            "price": 1.0, "quantity": 1.0, "notional": 1.0,
            "buyer_is_maker": False, "aggressor_side": "BUY", "raw_json": "{}",
        })
        ACTIVE_COLLECTOR_LEASE.reset(context_token)
        context_token = None
        assert sorted(row["trade_id"] for row in trade_store.recent("SPOT", symbol)) == [900001, 900003]
    finally:
        if context_token is not None:
            ACTIVE_COLLECTOR_LEASE.reset(context_token)
        with lease_store._connect() as connection:
            connection.execute(
                "DELETE FROM public.aggregate_trades WHERE market=%s AND symbol=%s",
                ("SPOT", symbol),
            )
            connection.execute(
                "DELETE FROM public.collector_leases WHERE collector_name=%s",
                (collector_name,),
            )
