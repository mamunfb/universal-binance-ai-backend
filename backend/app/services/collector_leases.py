from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import psycopg


class CollectorLeaseLostError(RuntimeError):
    """Raised when a collector attempts a write without its current database lease."""


def assert_collector_lease_owned(connection: Any, collector_name: str, owner_token: str) -> None:
    """Lock the lease row while a collector write transaction is in progress.

    FOR SHARE prevents a new owner from replacing the lease row until this write
    transaction commits. clock_timestamp() checks real wall-clock expiry rather
    than PostgreSQL's transaction-start timestamp.
    """
    row = connection.execute(
        """
        SELECT owner_token
        FROM public.collector_leases
        WHERE collector_name = %s
          AND owner_token = %s
          AND lease_expires_at > clock_timestamp()
        FOR SHARE
        """,
        (collector_name, owner_token),
    ).fetchone()
    if row is None:
        raise CollectorLeaseLostError(f"Collector lease is not owned: {collector_name}")


class CollectorLeaseStore:
    """PostgreSQL-backed single-owner leases shared by all application processes."""

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url.strip()
        if not self.database_url:
            raise ValueError("DATABASE_URL is required for distributed collector leases")

    def _connect(self):
        return psycopg.connect(
            self.database_url,
            sslmode=("disable" if "sslmode=disable" in self.database_url else "require"),
            connect_timeout=15,
        )

    def acquire(self, collector_name: str, owner_token: str, ttl_seconds: int) -> bool:
        if not collector_name.strip() or not owner_token.strip():
            raise ValueError("collector_name and owner_token must not be empty")
        if not 5 <= ttl_seconds <= 300:
            raise ValueError("ttl_seconds must be between 5 and 300")
        with self._connect() as connection:
            row = connection.execute(
                """
                INSERT INTO public.collector_leases (
                    collector_name, owner_token, lease_expires_at, updated_at
                )
                VALUES (%s, %s, NOW() + (%s * INTERVAL '1 second'), NOW())
                ON CONFLICT (collector_name) DO UPDATE SET
                    owner_token = EXCLUDED.owner_token,
                    lease_expires_at = NOW() + (%s * INTERVAL '1 second'),
                    updated_at = NOW()
                WHERE public.collector_leases.lease_expires_at <= NOW()
                   OR public.collector_leases.owner_token = EXCLUDED.owner_token
                RETURNING collector_name
                """,
                (collector_name, owner_token, ttl_seconds, ttl_seconds),
            ).fetchone()
        return row is not None

    def renew(self, collector_name: str, owner_token: str, ttl_seconds: int) -> bool:
        if not 5 <= ttl_seconds <= 300:
            raise ValueError("ttl_seconds must be between 5 and 300")
        with self._connect() as connection:
            row = connection.execute(
                """
                UPDATE public.collector_leases
                SET lease_expires_at = NOW() + (%s * INTERVAL '1 second'),
                    updated_at = NOW()
                WHERE collector_name = %s
                  AND owner_token = %s
                  AND lease_expires_at > NOW()
                RETURNING collector_name
                """,
                (ttl_seconds, collector_name, owner_token),
            ).fetchone()
        return row is not None

    def release(self, collector_name: str, owner_token: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                DELETE FROM public.collector_leases
                WHERE collector_name = %s AND owner_token = %s
                """,
                (collector_name, owner_token),
            )
            return cursor.rowcount == 1


class CollectorLeaseCoordinator:
    """Starts a collector only while this process owns its renewable DB lease."""

    def __init__(
        self,
        store: CollectorLeaseStore,
        collector_name: str,
        start_collector: Callable[[str], Any],
        stop_collector: Callable[[], Awaitable[Any]],
        *,
        owner_token: str,
        ttl_seconds: int = 30,
        heartbeat_seconds: int = 10,
        retry_seconds: int = 5,
    ) -> None:
        if not collector_name.strip() or not owner_token.strip():
            raise ValueError("collector_name and owner_token must not be empty")
        if not 5 <= ttl_seconds <= 300:
            raise ValueError("ttl_seconds must be between 5 and 300")
        if not 1 <= heartbeat_seconds < ttl_seconds:
            raise ValueError("heartbeat_seconds must be positive and less than lease TTL")
        if not 1 <= retry_seconds <= 60:
            raise ValueError("retry_seconds must be between 1 and 60")
        self.store = store
        self.collector_name = collector_name
        self.start_collector = start_collector
        self.stop_collector = stop_collector
        self.owner_token = owner_token
        self.ttl_seconds = ttl_seconds
        self.heartbeat_seconds = heartbeat_seconds
        self.retry_seconds = retry_seconds
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task | None = None
        self._owned = False
        self._collector_started = False
        self._state = "IDLE"
        self._last_error: str | None = None

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._stop_event.clear()
            self._task = asyncio.create_task(
                self._run(), name=f"collector-lease-{self.collector_name}"
            )

    async def stop(self) -> None:
        self._stop_event.set()
        task = self._task
        if task is not None:
            await task
        self._task = None

    async def _wait(self, seconds: int) -> bool:
        try:
            await asyncio.wait_for(self._stop_event.wait(), timeout=seconds)
            return True
        except asyncio.TimeoutError:
            return False

    async def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                acquired = await asyncio.to_thread(
                    self.store.acquire,
                    self.collector_name,
                    self.owner_token,
                    self.ttl_seconds,
                )
            except Exception as exc:
                self._state = "DEGRADED"
                self._last_error = type(exc).__name__
                if await self._wait(self.retry_seconds):
                    break
                continue

            if not acquired:
                self._state = "WAITING_FOR_LEASE"
                if await self._wait(self.retry_seconds):
                    break
                continue

            if self._stop_event.is_set():
                try:
                    await asyncio.to_thread(
                        self.store.release, self.collector_name, self.owner_token
                    )
                except Exception as exc:
                    self._state = "DEGRADED"
                    self._last_error = type(exc).__name__
                break

            self._owned = True
            self._state = "ACTIVE"
            self._last_error = None
            try:
                self.start_collector(self.owner_token)
                self._collector_started = True
                while not self._stop_event.is_set():
                    if await self._wait(self.heartbeat_seconds):
                        break
                    try:
                        renewed = await asyncio.to_thread(
                            self.store.renew,
                            self.collector_name,
                            self.owner_token,
                            self.ttl_seconds,
                        )
                    except Exception as exc:
                        self._state = "LEASE_LOST"
                        self._last_error = type(exc).__name__
                        break
                    if not renewed:
                        self._state = "LEASE_LOST"
                        self._last_error = "LEASE_RENEWAL_REJECTED"
                        break
            except Exception as exc:
                self._state = "DEGRADED"
                self._last_error = type(exc).__name__
            finally:
                try:
                    if self._collector_started:
                        await self.stop_collector()
                except Exception as exc:
                    self._state = "DEGRADED"
                    self._last_error = type(exc).__name__
                finally:
                    self._collector_started = False
                    try:
                        await asyncio.to_thread(
                            self.store.release, self.collector_name, self.owner_token
                        )
                    except Exception as exc:
                        self._state = "DEGRADED"
                        self._last_error = type(exc).__name__
                    self._owned = False

            if not self._stop_event.is_set() and await self._wait(self.retry_seconds):
                break

        if self._state not in {"DEGRADED", "LEASE_LOST"}:
            self._state = "STOPPED"

    def status(self) -> dict[str, Any]:
        return {
            "mode": "POSTGRESQL_LEASE",
            "state": self._state,
            "collector_name": self.collector_name,
            "lease_owned": self._owned,
            "lease_ttl_seconds": self.ttl_seconds,
            "heartbeat_seconds": self.heartbeat_seconds,
            "retry_seconds": self.retry_seconds,
            "last_error_type": self._last_error,
        }
