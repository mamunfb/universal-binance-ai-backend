from __future__ import annotations

import asyncio
import os
import uuid
import time
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
        assert store.acquire(collector_name, winner, 30) == winner_generation
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


@pytest.mark.asyncio
async def test_coordinator_started_collector_task_keeps_lease_context_in_thread():
    class FakeLeaseStore:
        def acquire(self, *_args):
            return 19

        def renew(self, *_args):
            return True

        def release(self, *_args):
            return True

    observed = asyncio.Event()
    observed_context = {}
    collector_task = None

    async def collector_worker():
        observed_context["task"] = ACTIVE_COLLECTOR_LEASE.get()
        observed_context["thread"] = await asyncio.to_thread(
            ACTIVE_COLLECTOR_LEASE.get
        )
        observed.set()
        await asyncio.Event().wait()

    def start_collector():
        nonlocal collector_task
        collector_task = asyncio.create_task(collector_worker())

    async def stop_collector():
        if collector_task is not None:
            collector_task.cancel()
            await asyncio.gather(collector_task, return_exceptions=True)

    coordinator = CollectorLeaseCoordinator(
        FakeLeaseStore(), "test-task-context", start_collector, stop_collector,
        owner_token="owner-task-context", ttl_seconds=5,
        heartbeat_seconds=1, retry_seconds=1,
    )
    coordinator.start()
    await asyncio.wait_for(observed.wait(), timeout=1)
    expected = CollectorLeaseContext("test-task-context", "owner-task-context", 19)
    assert observed_context["task"] == expected
    assert observed_context["thread"] == expected
    await coordinator.stop()
    assert coordinator.status()["state"] == "STOPPED"


def test_fenced_write_lock_blocks_expired_lease_takeover():
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is not configured")

    store = CollectorLeaseStore(database_url)
    collector_name = f"test-fence-lock-{uuid.uuid4().hex}"
    first_owner = f"owner-{uuid.uuid4().hex}"
    next_owner = f"owner-{uuid.uuid4().hex}"
    connection = None
    try:
        first_generation = store.acquire(collector_name, first_owner, 5)
        assert first_generation == 1

        # Keep the transaction (and its FOR SHARE row lock) open while the lease
        # expires. A takeover must wait for this fenced write transaction to end.
        connection = store._connect()
        assert_current_collector_lease(connection, collector_name)
        time.sleep(5.2)

        with ThreadPoolExecutor(max_workers=1) as pool:
            takeover = pool.submit(store.acquire, collector_name, next_owner, 30)
            time.sleep(0.25)
            assert takeover.done() is False
            connection.commit()
            connection.close()
            connection = None
            next_generation = takeover.result(timeout=3)

        assert next_generation == first_generation + 1
        assert store.release(collector_name, next_owner, next_generation) is True
    finally:
        if connection is not None:
            connection.close()
        with store._connect() as cleanup:
            cleanup.execute(
                "DELETE FROM public.collector_leases WHERE collector_name=%s",
                (collector_name,),
            )


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


def test_stale_lease_generation_cannot_write_aggregate_trade(monkeypatch):
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is not configured")

    import app.services.aggregate_trade_stream as aggregate_trade_stream
    from app.services.aggregate_trade_stream import AggregateTradeStore

    lease_store = CollectorLeaseStore(database_url)
    trade_store = AggregateTradeStore("unused.sqlite3", database_url)
    collector_name = f"test-aggregate-fence-{uuid.uuid4().hex}"
    monkeypatch.setattr(
        aggregate_trade_stream,
        "assert_current_collector_lease",
        lambda connection, _collector_name: assert_current_collector_lease(
            connection, collector_name
        ),
    )
    symbol = f"FENCE{uuid.uuid4().hex[:12].upper()}"
    first_owner = f"owner-{uuid.uuid4().hex}"
    next_owner = f"owner-{uuid.uuid4().hex}"
    context_token = None
    try:
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


def test_expired_lease_is_rejected_even_when_transaction_started_before_expiry():
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is not configured")

    store = CollectorLeaseStore(database_url)
    collector_name = f"test-clock-fence-{uuid.uuid4().hex}"
    owner = f"owner-{uuid.uuid4().hex}"
    generation = store.acquire(collector_name, owner, 30)
    assert generation is not None
    context_token = ACTIVE_COLLECTOR_LEASE.set(
        CollectorLeaseContext(collector_name, owner, generation)
    )
    connection = store._connect()
    try:
        # NOW() is fixed at transaction start. Start this transaction while the
        # lease is valid, then expire the lease from another connection.
        transaction_started_at = connection.execute("SELECT NOW() AS transaction_started_at").fetchone()["transaction_started_at"]
        with store._connect() as expiry_connection:
            expiry_connection.execute(
                """
                UPDATE public.collector_leases
                SET lease_expires_at = clock_timestamp() - INTERVAL '1 second'
                WHERE collector_name = %s
                """,
                (collector_name,),
            )

        with pytest.raises(CollectorLeaseLostError):
            assert_current_collector_lease(connection, collector_name)
        assert transaction_started_at is not None
    finally:
        connection.rollback()
        connection.close()
        ACTIVE_COLLECTOR_LEASE.reset(context_token)
        with store._connect() as cleanup_connection:
            cleanup_connection.execute(
                "DELETE FROM public.collector_leases WHERE collector_name=%s",
                (collector_name,),
            )


@pytest.mark.asyncio
async def test_lease_context_propagates_to_collector_tasks_and_worker_threads():
    lease = CollectorLeaseContext(
        "aggregate-trades:all", "owner-context-propagation", 42
    )
    context_token = ACTIVE_COLLECTOR_LEASE.set(lease)
    try:
        async def read_in_task():
            task_lease = ACTIVE_COLLECTOR_LEASE.get()
            thread_lease = await asyncio.to_thread(ACTIVE_COLLECTOR_LEASE.get)
            return task_lease, thread_lease

        task = asyncio.create_task(read_in_task())
        task_lease, thread_lease = await task
        assert task_lease == lease
        assert thread_lease == lease
    finally:
        ACTIVE_COLLECTOR_LEASE.reset(context_token)
