from __future__ import annotations

import asyncio
import os
import time
import uuid

import psycopg
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.services.collector_leases import (
    CollectorLeaseCoordinator, CollectorLeaseLostError, CollectorLeaseStore,
    assert_collector_lease_owned,
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
            results = list(pool.map(
                lambda owner: store.acquire(collector_name, owner, 30), owners
            ))
        assert sorted(results) == [False, True]
        winner = owners[results.index(True)]
        loser = owners[results.index(False)]
        assert store.renew(collector_name, winner, 30) is True
        assert store.renew(collector_name, loser, 30) is False
        assert store.release(collector_name, loser) is False
        assert store.release(collector_name, winner) is True
        assert store.acquire(collector_name, loser, 30) is True
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
        assert store.acquire(collector_name, first_owner, 30) is True
        with store._connect() as connection:
            connection.execute(
                """
                UPDATE public.collector_leases
                SET lease_expires_at = NOW() - INTERVAL '1 second'
                WHERE collector_name=%s
                """,
                (collector_name,),
            )
        assert store.renew(collector_name, first_owner, 30) is False
        assert store.acquire(collector_name, next_owner, 30) is True
        assert store.release(collector_name, first_owner) is False
        assert store.release(collector_name, next_owner) is True
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
            return True

        def renew(self, *_args):
            return True

        def release(self, *_args):
            self.released = True
            return True

    started = asyncio.Event()
    stopped = asyncio.Event()
    store = FakeLeaseStore()

    started_tokens = []

    def start_collector(owner_token):
        started_tokens.append(owner_token)
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
    assert started_tokens == ["owner-1"]
    await coordinator.stop()
    await asyncio.wait_for(stopped.wait(), timeout=1)

    assert store.released is True
    assert coordinator.status()["state"] == "STOPPED"
    assert coordinator.status()["lease_owned"] is False


@pytest.mark.asyncio
async def test_lease_coordinator_stops_collector_when_lease_renewal_is_rejected():
    class FakeLeaseStore:
        def acquire(self, *_args):
            return True

        def renew(self, *_args):
            return False

        def release(self, *_args):
            return True

    started = asyncio.Event()
    stopped = asyncio.Event()

    started_tokens = []

    def start_collector(owner_token):
        started_tokens.append(owner_token)
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
    assert started_tokens == ["owner-2"]
    await coordinator.stop()

    assert coordinator.status()["state"] == "LEASE_LOST"
    assert coordinator.status()["lease_owned"] is False



def test_write_fencing_rejects_previous_owner_after_lease_takeover():
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is not configured")

    store = CollectorLeaseStore(database_url)
    collector_name = f"test-fencing-{uuid.uuid4().hex}"
    old_owner = f"owner-{uuid.uuid4().hex}"
    new_owner = f"owner-{uuid.uuid4().hex}"
    try:
        assert store.acquire(collector_name, old_owner, 30) is True
        with store._connect() as connection:
            assert_collector_lease_owned(connection, collector_name, old_owner)

        with store._connect() as connection:
            connection.execute(
                """
                UPDATE public.collector_leases
                SET lease_expires_at = NOW() - INTERVAL '1 second'
                WHERE collector_name=%s
                """,
                (collector_name,),
            )
        assert store.acquire(collector_name, new_owner, 30) is True

        with store._connect() as connection:
            with pytest.raises(CollectorLeaseLostError):
                assert_collector_lease_owned(connection, collector_name, old_owner)

        with store._connect() as connection:
            assert_collector_lease_owned(connection, collector_name, new_owner)
    finally:
        with store._connect() as connection:
            connection.execute(
                "DELETE FROM public.collector_leases WHERE collector_name=%s",
                (collector_name,),
            )


def test_write_transaction_lock_blocks_expired_lease_takeover_until_commit():
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is not configured")

    import threading

    store = CollectorLeaseStore(database_url)
    collector_name = f"test-fencing-lock-{uuid.uuid4().hex}"
    old_owner = f"owner-{uuid.uuid4().hex}"
    new_owner = f"owner-{uuid.uuid4().hex}"
    connection = None
    try:
        assert store.acquire(collector_name, old_owner, 5) is True
        connection = store._connect()
        assert_collector_lease_owned(connection, collector_name, old_owner)

        # Keep the authorized write transaction open until the lease expires.
        time.sleep(5.2)

        takeover_connection_ready = threading.Event()
        takeover_backend_pid: dict[str, int] = {}
        original_connect = store._connect

        def tracked_connect():
            takeover_connection = original_connect()
            takeover_backend_pid["pid"] = takeover_connection.info.backend_pid
            takeover_connection_ready.set()
            return takeover_connection

        # Observe the actual backend used by acquire(), without changing its SQL.
        store._connect = tracked_connect
        with ThreadPoolExecutor(max_workers=1) as pool:
            takeover = pool.submit(store.acquire, collector_name, new_owner, 30)
            try:
                assert takeover_connection_ready.wait(timeout=3)
                backend_pid = takeover_backend_pid["pid"]

                # Confirm PostgreSQL reports a real blocking lock, not just a slow thread.
                deadline = time.monotonic() + 5
                blocking_pids: list[int] = []
                while time.monotonic() < deadline:
                    with original_connect() as monitor:
                        blocking_pids = monitor.execute(
                            "SELECT pg_blocking_pids(%s)", (backend_pid,)
                        ).fetchone()[0]
                    if blocking_pids:
                        break
                    if takeover.done():
                        break
                    time.sleep(0.025)

                assert blocking_pids, (
                    "Expected PostgreSQL to report the takeover backend as blocked "
                    "by the open FOR SHARE write transaction"
                )
                assert takeover.done() is False

                connection.commit()
                assert takeover.result(timeout=5) is True
            finally:
                # Always release FOR SHARE before the executor waits for its worker.
                connection.rollback()

        store._connect = original_connect
        with original_connect() as check:
            with pytest.raises(CollectorLeaseLostError):
                assert_collector_lease_owned(check, collector_name, old_owner)
            assert_collector_lease_owned(check, collector_name, new_owner)
    finally:
        store._connect = original_connect if "original_connect" in locals() else store._connect
        if connection is not None:
            connection.rollback()
            connection.close()
        with store._connect() as cleanup:
            cleanup.execute(
                "DELETE FROM public.collector_leases WHERE collector_name=%s",
                (collector_name,),
            )


def test_aggregate_trade_store_rejects_stale_lease_owner():
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is not configured")

    from app.services.aggregate_trade_stream import AggregateTradeStore

    lease_store = CollectorLeaseStore(database_url)
    trade_store = AggregateTradeStore("", database_url)
    collector_name = "aggregate-trades:all"
    old_owner = f"owner-{uuid.uuid4().hex}"
    new_owner = f"owner-{uuid.uuid4().hex}"
    symbol = f"LEASE{uuid.uuid4().hex[:10].upper()}"
    trade_id = time.time_ns() % 9_000_000_000_000_000
    row = {
        "market": "SPOT",
        "symbol": symbol,
        "trade_id": trade_id,
        "event_time_ms": 1,
        "trade_time_ms": 1,
        "price": 1.0,
        "quantity": 1.0,
        "notional": 1.0,
        "buyer_is_maker": False,
        "aggressor_side": "BUY",
        "raw_json": "{}",
    }
    try:
        assert lease_store.acquire(collector_name, old_owner, 30) is True
        with lease_store._connect() as connection:
            connection.execute(
                """
                UPDATE public.collector_leases
                SET lease_expires_at = clock_timestamp() - INTERVAL '1 second'
                WHERE collector_name=%s
                """,
                (collector_name,),
            )
        assert lease_store.acquire(collector_name, new_owner, 30) is True

        with pytest.raises(CollectorLeaseLostError):
            trade_store.insert(row, old_owner)

        trade_store.insert(row, new_owner)
        persisted = trade_store.recent("SPOT", symbol, limit=10)
        assert any(item["trade_id"] == trade_id for item in persisted)
    finally:
        with psycopg.connect(database_url) as connection:
            connection.execute(
                "DELETE FROM public.aggregate_trades WHERE market=%s AND symbol=%s AND trade_id=%s",
                ("SPOT", symbol, trade_id),
            )
            connection.execute(
                "DELETE FROM public.collector_leases WHERE collector_name=%s AND owner_token IN (%s, %s)",
                (collector_name, old_owner, new_owner),
            )
