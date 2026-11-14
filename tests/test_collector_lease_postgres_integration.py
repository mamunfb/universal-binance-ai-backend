"""Real PostgreSQL tests for collector lease/fencing primitives.

The CI workflow supplies TEST_DATABASE_URL and applies all SQL migrations first.
"""
from __future__ import annotations

import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError

import psycopg
import pytest

from app.services.collector_lease import PostgresCollectorLease


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
