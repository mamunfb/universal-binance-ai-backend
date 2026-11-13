from __future__ import annotations

import asyncio
import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.services.collector_leases import CollectorLeaseCoordinator, CollectorLeaseStore


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

    def start_collector():
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
