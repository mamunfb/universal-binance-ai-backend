"""PostgreSQL lease primitives for future multi-instance collector coordination.

These primitives do not start or guard collectors by themselves. Every collector
write must call lock_if_owned() and perform its data mutation on the same
connection/transaction before this module is safe to wire into runtime tasks.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import psycopg
from psycopg.rows import dict_row


class CollectorLeaseLostError(RuntimeError):
    """Raised when a collector attempts a write without its current lease."""


@dataclass(frozen=True)
class CollectorLease:
    lease_name: str
    owner_id: UUID
    fencing_token: int
    lease_expires_at: datetime


class PostgresCollectorLease:
    """Acquire, renew, and release a single named lease in PostgreSQL."""

    def __init__(
        self,
        database_url: str,
        lease_name: str,
        owner_id: UUID | None = None,
        ttl_seconds: int = 30,
    ) -> None:
        if not isinstance(database_url, str) or not database_url.strip():
            raise ValueError("A PostgreSQL database URL is required")
        if not isinstance(lease_name, str) or not lease_name.strip() or len(lease_name) > 160:
            raise ValueError("lease_name must contain 1 to 160 non-whitespace characters")
        if isinstance(ttl_seconds, bool) or not isinstance(ttl_seconds, int) or not 5 <= ttl_seconds <= 3600:
            raise ValueError("ttl_seconds must be an integer between 5 and 3600")
        self.database_url = database_url.strip()
        self.lease_name = lease_name.strip()
        self.owner_id = owner_id if owner_id is not None else uuid4()
        if not isinstance(self.owner_id, UUID):
            raise ValueError("owner_id must be a UUID")
        self.ttl_seconds = ttl_seconds

    def _connect(self):
        return psycopg.connect(
            self.database_url,
            sslmode=("disable" if "sslmode=disable" in self.database_url else "require"),
            connect_timeout=15,
            row_factory=dict_row,
        )

    def acquire(self) -> CollectorLease | None:
        """Acquire an unowned/expired lease; return None while another owner is live."""
        with self._connect() as connection:
            row = connection.execute(
                """
                INSERT INTO public.collector_leases (
                    lease_name, owner_id, fencing_token, lease_expires_at, updated_at
                )
                VALUES (
                    %s, %s, 1,
                    clock_timestamp() + (%s * INTERVAL '1 second'),
                    clock_timestamp()
                )
                ON CONFLICT (lease_name) DO UPDATE SET
                    owner_id = EXCLUDED.owner_id,
                    fencing_token = CASE
                        WHEN collector_leases.owner_id = EXCLUDED.owner_id
                         AND collector_leases.lease_expires_at > clock_timestamp()
                        THEN collector_leases.fencing_token
                        ELSE collector_leases.fencing_token + 1
                    END,
                    lease_expires_at = EXCLUDED.lease_expires_at,
                    updated_at = clock_timestamp()
                WHERE collector_leases.lease_expires_at <= clock_timestamp()
                   OR collector_leases.owner_id = EXCLUDED.owner_id
                RETURNING owner_id, fencing_token, lease_expires_at
                """,
                (self.lease_name, self.owner_id, self.ttl_seconds),
            ).fetchone()
        if row is None:
            return None
        return CollectorLease(
            lease_name=self.lease_name,
            owner_id=row["owner_id"],
            fencing_token=int(row["fencing_token"]),
            lease_expires_at=row["lease_expires_at"],
        )

    def renew(self, lease: CollectorLease) -> CollectorLease | None:
        """Renew only a still-live lease held by this exact owner and fencing token."""
        self._validate_lease(lease)
        with self._connect() as connection:
            row = connection.execute(
                """
                UPDATE public.collector_leases
                   SET lease_expires_at = clock_timestamp() + (%s * INTERVAL '1 second'),
                       updated_at = clock_timestamp()
                 WHERE lease_name = %s
                   AND owner_id = %s
                   AND fencing_token = %s
                   AND lease_expires_at > clock_timestamp()
                RETURNING owner_id, fencing_token, lease_expires_at
                """,
                (self.ttl_seconds, lease.lease_name, lease.owner_id, lease.fencing_token),
            ).fetchone()
        if row is None:
            return None
        return CollectorLease(
            lease_name=lease.lease_name,
            owner_id=row["owner_id"],
            fencing_token=int(row["fencing_token"]),
            lease_expires_at=row["lease_expires_at"],
        )

    def release(self, lease: CollectorLease) -> bool:
        """Expire, but do not delete, the row so fencing tokens remain monotonic."""
        self._validate_lease(lease)
        with self._connect() as connection:
            row = connection.execute(
                """
                UPDATE public.collector_leases
                   SET lease_expires_at = clock_timestamp(),
                       updated_at = clock_timestamp()
                 WHERE lease_name = %s
                   AND owner_id = %s
                   AND fencing_token = %s
                   AND lease_expires_at = %s
                RETURNING lease_name
                """,
                (
                    lease.lease_name, lease.owner_id, lease.fencing_token,
                    lease.lease_expires_at,
                ),
            ).fetchone()
        return row is not None

    @staticmethod
    def lock_if_owned(connection: Any, lease: CollectorLease) -> bool:
        """Fence a write by locking and validating its lease in the same transaction.

        Call this immediately before the protected INSERT/UPDATE using the same
        connection. FOR SHARE conflicts with lease-row takeover updates, so a new
        owner cannot advance the fencing token until this transaction commits.
        Never hold this transaction open while making network requests.
        """
        if not isinstance(lease, CollectorLease):
            raise ValueError("A valid CollectorLease is required")
        row = connection.execute(
            """
            SELECT 1
              FROM public.collector_leases
             WHERE lease_name = %s
               AND owner_id = %s
               AND fencing_token = %s
               AND lease_expires_at > clock_timestamp()
             FOR SHARE
            """,
            (lease.lease_name, lease.owner_id, lease.fencing_token),
        ).fetchone()
        return row is not None

    def _validate_lease(self, lease: CollectorLease) -> None:
        if (
            not isinstance(lease, CollectorLease)
            or lease.lease_name != self.lease_name
            or lease.owner_id != self.owner_id
            or isinstance(lease.fencing_token, bool)
            or not isinstance(lease.fencing_token, int)
            or lease.fencing_token < 1
        ):
            raise ValueError("Lease does not belong to this collector owner")
