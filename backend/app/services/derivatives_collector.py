from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any, Callable

from app.services.collector_lease import (
    CollectorLease,
    CollectorLeaseLostError,
    PostgresCollectorLease,
)
from app.services.funding_rates import FundingRateStore
from app.services.open_interest import OPEN_INTEREST_PERIODS, OpenInterestStore


def parse_derivatives_jobs(raw: str) -> list[dict[str, str]]:
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("DERIVATIVES_COLLECTOR_JOBS must be a JSON array") from exc
    if not isinstance(value, list) or len(value) > 100:
        raise ValueError("DERIVATIVES_COLLECTOR_JOBS must contain at most 100 jobs")
    jobs: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("Each derivatives collector job must be an object")
        kind = str(item.get("type", "")).upper()
        symbol = str(item.get("symbol", "")).strip().upper()
        period = str(item.get("period", "1h"))
        if kind not in {"FUNDING_RATE", "OPEN_INTEREST"}:
            raise ValueError("Job type must be FUNDING_RATE or OPEN_INTEREST")
        if not symbol or len(symbol) > 40:
            raise ValueError("Each derivatives job requires a valid symbol")
        if kind == "FUNDING_RATE":
            period = ""
        elif period not in OPEN_INTEREST_PERIODS:
            raise ValueError("Unsupported open-interest period in collector job")
        key = (kind, symbol, period)
        if key in seen:
            raise ValueError("Duplicate derivatives collector job")
        seen.add(key)
        jobs.append({"type": kind, "symbol": symbol, "period": period})
    return jobs


class DerivativesHistoryCollector:
    """Optional sequential collector for USD-M funding and open-interest history."""

    def __init__(
        self, funding_store: FundingRateStore, open_interest_store: OpenInterestStore,
        provider_factory: Callable[[str], Any], jobs_json: str,
        poll_seconds: int = 60, funding_limit: int = 1000,
        open_interest_limit: int = 500,
        lease_database_url: str = "",
        lease_name: str = "derivatives-history-collector",
        lease_ttl_seconds: int = 30,
    ) -> None:
        if not 10 <= poll_seconds <= 3600:
            raise ValueError("poll_seconds must be between 10 and 3600")
        if not 1 <= funding_limit <= 1000:
            raise ValueError("funding_limit must be between 1 and 1000")
        if not 1 <= open_interest_limit <= 500:
            raise ValueError("open_interest_limit must be between 1 and 500")
        self.funding_store = funding_store
        self.open_interest_store = open_interest_store
        self.provider_factory = provider_factory
        self.jobs = parse_derivatives_jobs(jobs_json)
        self.poll_seconds = poll_seconds
        self.funding_limit = funding_limit
        self.open_interest_limit = open_interest_limit
        self._lease_coordinator = (
            PostgresCollectorLease(
                lease_database_url, lease_name, ttl_seconds=lease_ttl_seconds
            )
            if lease_database_url.strip()
            else None
        )
        self._lease: CollectorLease | None = None
        self._lease_lost: asyncio.Event | None = None
        self._lease_state = "NOT_REQUIRED" if self._lease_coordinator is None else "WAITING"
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()
        self._lock = asyncio.Lock()
        self._status: dict[str, Any] = {
            "status": "IDLE", "enabled": True, "job_count": len(self.jobs),
            "poll_seconds": poll_seconds, "cycles": 0, "successful_jobs": 0,
            "failed_jobs": 0, "last_cycle_at": None, "last_results": [],
        }

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._stop_event.clear()
            self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is not None:
            await self._task
            self._task = None
        if self._lease_state != "LOST":
            self._status["status"] = "STOPPED"

    async def _wait_for_stop_or_lease_loss(self, timeout: float) -> None:
        waits = [asyncio.create_task(self._stop_event.wait())]
        if self._lease_lost is not None:
            waits.append(asyncio.create_task(self._lease_lost.wait()))
        try:
            await asyncio.wait(waits, timeout=timeout, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for task in waits:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*waits, return_exceptions=True)

    async def _renew_lease_loop(self) -> None:
        assert self._lease_coordinator is not None
        assert self._lease_lost is not None
        interval = max(1.0, self._lease_coordinator.ttl_seconds / 3)
        while not self._lease_lost.is_set() and not self._stop_event.is_set():
            try:
                await asyncio.wait_for(self._lease_lost.wait(), timeout=interval)
                return
            except asyncio.TimeoutError:
                pass
            lease = self._lease
            if lease is None:
                self._lease_state = "LOST"
                self._lease_lost.set()
                return
            try:
                renewed = await asyncio.to_thread(self._lease_coordinator.renew, lease)
            except Exception as exc:
                self._status["last_lease_error_type"] = type(exc).__name__
                renewed = None
            if renewed is None:
                self._lease_state = "LOST"
                self._status["status"] = "LEASE_LOST"
                self._lease_lost.set()
                return
            self._lease = renewed

    async def _run_loop(self) -> None:
        self._status["status"] = "RUNNING"
        if self._lease_coordinator is None:
            while not self._stop_event.is_set():
                try:
                    await self.run_once()
                except Exception:
                    self._status["status"] = "DEGRADED"
                await self._wait_for_stop_or_lease_loss(self.poll_seconds)
            self._status["status"] = "STOPPED"
            return

        while not self._stop_event.is_set():
            try:
                lease = await asyncio.to_thread(self._lease_coordinator.acquire)
            except Exception as exc:
                self._lease_state = "ACQUIRE_FAILED"
                self._status["last_lease_error_type"] = type(exc).__name__
                await self._wait_for_stop_or_lease_loss(self.poll_seconds)
                continue
            if self._stop_event.is_set():
                if lease is not None:
                    await asyncio.to_thread(self._lease_coordinator.release, lease)
                break
            if lease is None:
                self._lease_state = "HELD_BY_OTHER"
                self._status["status"] = "WAITING_FOR_LEASE"
                await self._wait_for_stop_or_lease_loss(self.poll_seconds)
                continue

            self._lease = lease
            self._lease_lost = asyncio.Event()
            self._lease_state = "OWNED"
            self._status["status"] = "RUNNING"
            renew_task = asyncio.create_task(self._renew_lease_loop())
            try:
                while not self._stop_event.is_set() and not self._lease_lost.is_set():
                    await self.run_once()
                    if self._stop_event.is_set() or self._lease_lost.is_set():
                        break
                    await self._wait_for_stop_or_lease_loss(self.poll_seconds)
            except Exception:
                self._status["status"] = "DEGRADED"
            finally:
                renew_task.cancel()
                await asyncio.gather(renew_task, return_exceptions=True)
                owned_lease = self._lease
                lost = self._lease_lost.is_set()
                self._lease = None
                self._lease_lost = None
                if lost:
                    self._lease_state = "LOST"
                    self._status["status"] = "LEASE_LOST"
                elif owned_lease is not None:
                    try:
                        released = await asyncio.to_thread(
                            self._lease_coordinator.release, owned_lease
                        )
                        self._lease_state = "RELEASED" if released else "RELEASE_FAILED"
                    except Exception as exc:
                        self._lease_state = "RELEASE_FAILED"
                        self._status["last_lease_error_type"] = type(exc).__name__
            if self._lease_state == "LOST":
                break
        if self._lease_state != "LOST":
            self._status["status"] = "STOPPED"

    async def run_once(self) -> dict[str, Any]:
        async with self._lock:
            results = []
            for job in self.jobs:
                if self._lease_lost is not None and self._lease_lost.is_set():
                    break
                try:
                    result = await self._collect_job(job)
                    results.append(result)
                    self._status["successful_jobs"] += 1
                except CollectorLeaseLostError as exc:
                    self._lease_state = "LOST"
                    self._status["status"] = "LEASE_LOST"
                    self._status["last_lease_error_type"] = type(exc).__name__
                    if self._lease_lost is not None:
                        self._lease_lost.set()
                    results.append({
                        "status": "FAILED", **job,
                        "error_type": type(exc).__name__,
                    })
                    self._status["failed_jobs"] += 1
                    break
                except Exception as exc:
                    results.append({
                        "status": "FAILED", **job,
                        "error_type": type(exc).__name__,
                    })
                    self._status["failed_jobs"] += 1
            self._status["cycles"] += 1
            self._status["last_cycle_at"] = datetime.now(timezone.utc).isoformat()
            self._status["last_results"] = results
            self._status["status"] = (
                "LEASE_LOST" if self._lease_lost is not None and self._lease_lost.is_set()
                else "DEGRADED" if any(x["status"] == "FAILED" for x in results)
                else "RUNNING"
            )
            return self.status()

    async def _collect_job(self, job: dict[str, str]) -> dict[str, Any]:
        provider = self.provider_factory("USD_M")
        symbol = job["symbol"]
        if job["type"] == "FUNDING_RATE":
            history = await asyncio.to_thread(self.funding_store.history, "USD_M", symbol, limit=1)
            latest = history["events"][-1]["funding_time_ms"] if history["events"] else None
            rows = await provider.funding_rate(
                symbol, limit=self.funding_limit, start_time_ms=latest,
            )
            if not rows:
                return {"status": "NO_NEW_DATA", **job, "received_count": 0}
            if self._lease_lost is not None and self._lease_lost.is_set():
                raise CollectorLeaseLostError("Derivatives collector lease was lost before funding write")
            return await asyncio.to_thread(
                self.funding_store.save, "USD_M", symbol, rows,
                source="Binance USD-M public REST API (scheduled collector)",
                lease=self._lease,
            )
        period = job["period"]
        history = await asyncio.to_thread(self.open_interest_store.history, "USD_M", symbol, period, limit=1)
        latest = history["records"][-1]["timestamp_ms"] if history["records"] else None
        rows = await provider.open_interest_history(
            symbol, period=period, limit=self.open_interest_limit, start_time_ms=latest,
        )
        if not rows:
            return {"status": "NO_NEW_DATA", **job, "received_count": 0}
        if self._lease_lost is not None and self._lease_lost.is_set():
            raise CollectorLeaseLostError("Derivatives collector lease was lost before open-interest write")
        return await asyncio.to_thread(
            self.open_interest_store.save, "USD_M", symbol, period, rows,
            source="Binance USD-M public REST API (scheduled collector)",
            lease=self._lease,
        )

    def status(self) -> dict[str, Any]:
        return {
            **self._status,
            "jobs": self.jobs,
            "lease_state": self._lease_state,
            "lease_name": (
                self._lease_coordinator.lease_name
                if self._lease_coordinator is not None else None
            ),
            "lease_fencing_token": (
                self._lease.fencing_token if self._lease is not None else None
            ),
            "warning": (
                "PostgreSQL lease fencing covers scheduled derivatives history writes only; "
                "manual collection endpoints and other collector families are not coordinated."
                if self._lease_coordinator is not None else
                "SQLite-backed derivatives collection remains single-process-only."
            ),
        }
