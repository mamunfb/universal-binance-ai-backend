from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Any

import psycopg


@dataclass(frozen=True)
class CollectorLeaseContext:
    collector_name: str
    owner_token: str
    lease_generation: int


ACTIVE_COLLECTOR_LEASE: ContextVar[CollectorLeaseContext | None] = ContextVar(
    "active_collector_lease", default=None
)


class CollectorLeaseLostError(RuntimeError):
    """Raised when a collector write is attempted with a stale lease generation."""


def assert_current_collector_lease(connection: Any, collector_name: str) -> None:
    """Fence a PostgreSQL write inside the same transaction as the data mutation.

    FOR SHARE keeps a concurrent lease takeover from changing the generation until
    this write transaction commits. A stale generation cannot pass this check.
    """
    lease = ACTIVE_COLLECTOR_LEASE.get()
    if lease is None:
        return
    if lease.collector_name != collector_name:
        raise CollectorLeaseLostError(
            f"Active lease {lease.collector_name!r} cannot write as {collector_name!r}"
        )
    row = connection.execute(
        """
        SELECT lease_generation
        FROM public.collector_leases
        WHERE collector_name = %s
          AND owner_token = %s
          AND lease_generation = %s
          AND lease_expires_at > NOW()
        FOR SHARE
        """,
        (lease.collector_name, lease.owner_token, lease.lease_generation),
    ).fetchone()
    if row is None:
        raise CollectorLeaseLostError(
            f"Collector lease is no longer current: {collector_name}"
        )


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

    def acquire(self, collector_name: str, owner_token: str, ttl_seconds: int) -> int | None:
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
                    lease_generation = CASE
                        WHEN public.collector_leases.owner_token = EXCLUDED.owner_token
                            THEN public.collector_leases.lease_generation
                        ELSE public.collector_leases.lease_generation + 1
                    END,
                    lease_expires_at = NOW() + (%s * INTERVAL '1 second'),
                    updated_at = NOW()
                WHERE public.collector_leases.lease_expires_at <= NOW()
                   OR public.collector_leases.owner_token = EXCLUDED.owner_token
                RETURNING lease_generation
                """,
                (collector_name, owner_token, ttl_seconds, ttl_seconds),
            ).fetchone()
        return int(row["lease_generation"]) if row is not None else None

    def renew(
        self, collector_name: str, owner_token: str,
        lease_generation: int, ttl_seconds: int,
    ) -> bool:
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
                  AND lease_generation = %s
                  AND lease_expires_at > NOW()
                RETURNING collector_name
                """,
                (ttl_seconds, collector_name, owner_token, lease_generation),
            ).fetchone()
        return row is not None

    def release(
        self, collector_name: str, owner_token: str, lease_generation: int
    ) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE public.collector_leases
                SET lease_expires_at = NOW(), updated_at = NOW()
                WHERE collector_name = %s
                  AND owner_token = %s
                  AND lease_generation = %s
                """,
                (collector_name, owner_token, lease_generation),
            )
            return cursor.rowcount == 1


class CollectorLeaseCoordinator:
    """Starts a collector only while this process owns its renewable DB lease."""

    def __init__(
        self,
        store: CollectorLeaseStore,
        collector_name: str,
        start_collector: Callable[[], Any],
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
        self._lease_generation: int | None = None
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
                generation = await asyncio.to_thread(
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

            if generation is None:
                self._state = "WAITING_FOR_LEASE"
                if await self._wait(self.retry_seconds):
                    break
                continue

            if self._stop_event.is_set():
                try:
                    await asyncio.to_thread(
                        self.store.release, self.collector_name,
                        self.owner_token, generation,
                    )
                except Exception as exc:
                    self._state = "DEGRADED"
                    self._last_error = type(exc).__name__
                break

            self._owned = True
            self._lease_generation = generation
            self._state = "ACTIVE"
            self._last_error = None
            context_token: Token | None = ACTIVE_COLLECTOR_LEASE.set(
                CollectorLeaseContext(self.collector_name, self.owner_token, generation)
            )
            try:
                self.start_collector()
                self._collector_started = True
                while not self._stop_event.is_set():
                    if await self._wait(self.heartbeat_seconds):
                        break
                    try:
                        renewed = await asyncio.to_thread(
                            self.store.renew,
                            self.collector_name,
                            self.owner_token,
                            generation,
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
                    if context_token is not None:
                        ACTIVE_COLLECTOR_LEASE.reset(context_token)
                    try:
                        await asyncio.to_thread(
                            self.store.release, self.collector_name,
                            self.owner_token, generation,
                        )
                    except Exception as exc:
                        self._state = "DEGRADED"
                        self._last_error = type(exc).__name__
                    self._owned = False
                    self._lease_generation = None

            if not self._stop_event.is_set() and await self._wait(self.retry_seconds):
                break

        if self._state not in {"DEGRADED", "LEASE_LOST"}:
            self._state = "STOPPED"

    def status(self) -> dict[str, Any]:
        return {
            "mode": "POSTGRESQL_LEASE_WITH_FENCING",
            "state": self._state,
            "collector_name": self.collector_name,
            "lease_owned": self._owned,
            "lease_generation": self._lease_generation,
            "lease_ttl_seconds": self.ttl_seconds,
            "heartbeat_seconds": self.heartbeat_seconds,
            "retry_seconds": self.retry_seconds,
            "last_error_type": self._last_error,
        }
