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
from app.services.historical_klines import HistoricalKlineStore

_INTERVALS = {
    "1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h",
    "6h", "8h", "12h", "1d", "3d", "1w", "1M",
}
_MARKETS = {"SPOT", "USD_M", "COIN_M"}


def parse_collector_jobs(raw: str) -> list[dict[str, str]]:
    """Parse an explicit JSON allow-list; never auto-subscribe to every market."""
    try:
        values = json.loads(raw or "[]")
    except json.JSONDecodeError as exc:
        raise ValueError("HISTORICAL_COLLECTOR_JOBS must be valid JSON") from exc
    if not isinstance(values, list):
        raise ValueError("HISTORICAL_COLLECTOR_JOBS must be a JSON array")
    jobs: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in values:
        if not isinstance(item, dict):
            raise ValueError("Each historical collector job must be an object")
        market = str(item.get("market", "")).upper()
        symbol = str(item.get("symbol", "")).strip().upper()
        interval = str(item.get("interval", "1h"))
        if market not in _MARKETS or not symbol or interval not in _INTERVALS:
            raise ValueError("Each job requires a supported market, symbol, and interval")
        key = (market, symbol, interval)
        if key in seen:
            raise ValueError(f"Duplicate historical collector job: {key}")
        seen.add(key)
        jobs.append({"market": market, "symbol": symbol, "interval": interval})
    if len(jobs) > 100:
        raise ValueError("At most 100 historical collector jobs are allowed")
    return jobs


class HistoricalKlineCollector:
    """Opt-in sequential collector that resumes from the latest stored candle."""

    def __init__(
        self,
        store: HistoricalKlineStore,
        spot_provider_factory: Callable[[], Any],
        futures_provider_factory: Callable[[str], Any],
        jobs_json: str = "[]",
        poll_seconds: int = 30,
        initial_limit: int = 500,
        lease_database_url: str = "",
        lease_name: str = "historical-kline-collector",
        lease_ttl_seconds: int = 30,
    ) -> None:
        self.store = store
        self.spot_provider_factory = spot_provider_factory
        self.futures_provider_factory = futures_provider_factory
        self.jobs = parse_collector_jobs(jobs_json)
        if not 10 <= poll_seconds <= 3600:
            raise ValueError("poll_seconds must be between 10 and 3600")
        if not 1 <= initial_limit <= 1500:
            raise ValueError("initial_limit must be between 1 and 1500")
        self.poll_seconds = poll_seconds
        self.initial_limit = initial_limit
        self._lease_coordinator = (
            PostgresCollectorLease(
                lease_database_url,
                lease_name,
                ttl_seconds=lease_ttl_seconds,
            )
            if lease_database_url.strip()
            else None
        )
        self._lease: CollectorLease | None = None
        self._lease_lost: asyncio.Event | None = None
        self._lease_state = "NOT_REQUIRED" if self._lease_coordinator is None else "WAITING"
        self._task: asyncio.Task | None = None
        self._running = False
        self._last_cycle_at: str | None = None
        self._last_success_at: str | None = None
        self._last_error: str | None = None
        self._cycles = 0
        self._successes = 0
        self._failures = 0
        self._last_results: list[dict[str, Any]] = []

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        task = self._task
        self._task = None
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._running = False

    async def _run_loop(self) -> None:
        if self._lease_coordinator is None:
            while True:
                try:
                    await self.run_once()
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    self._last_error = type(exc).__name__
                await asyncio.sleep(self.poll_seconds)

        while True:
            acquire_task = asyncio.create_task(
                asyncio.to_thread(self._lease_coordinator.acquire)
            )
            try:
                lease = await asyncio.shield(acquire_task)
            except asyncio.CancelledError:
                # Do not orphan a lease if shutdown races with a blocking DB acquire.
                try:
                    acquired_during_shutdown = await acquire_task
                    if acquired_during_shutdown is not None:
                        await asyncio.to_thread(
                            self._lease_coordinator.release, acquired_during_shutdown
                        )
                finally:
                    raise
            except Exception as exc:
                self._lease_state = "ACQUIRE_FAILED"
                self._last_error = type(exc).__name__
                await asyncio.sleep(self.poll_seconds)
                continue
            if lease is None:
                self._lease_state = "HELD_BY_OTHER"
                await asyncio.sleep(self.poll_seconds)
                continue

            self._lease = lease
            self._lease_lost = asyncio.Event()
            self._lease_state = "OWNED"
            renew_task = asyncio.create_task(self._renew_lease_loop())
            try:
                while not self._lease_lost.is_set():
                    await self.run_once()
                    if self._lease_lost.is_set():
                        break
                    try:
                        await asyncio.wait_for(
                            self._lease_lost.wait(), timeout=self.poll_seconds
                        )
                    except asyncio.TimeoutError:
                        pass
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._last_error = type(exc).__name__
            finally:
                renew_task.cancel()
                try:
                    await renew_task
                except asyncio.CancelledError:
                    pass
                owned_lease = self._lease
                lease_was_lost = self._lease_lost.is_set()
                self._lease = None
                self._lease_lost = None
                if lease_was_lost:
                    self._lease_state = "LOST"
                elif owned_lease is not None:
                    try:
                        released = await asyncio.to_thread(
                            self._lease_coordinator.release, owned_lease
                        )
                        self._lease_state = "RELEASED" if released else "LOST"
                    except Exception as exc:
                        self._lease_state = "RELEASE_FAILED"
                        self._last_error = type(exc).__name__
            if self._lease_state == "LOST":
                # A failed heartbeat is a terminal safety event for this process.
                # Do not silently reacquire and restart work after ownership loss.
                return
            if self._lease_state == "RELEASE_FAILED":
                await asyncio.sleep(self.poll_seconds)

    async def _renew_lease_loop(self) -> None:
        assert self._lease_coordinator is not None
        assert self._lease_lost is not None
        interval = max(1.0, self._lease_coordinator.ttl_seconds / 3)
        while not self._lease_lost.is_set():
            await asyncio.sleep(interval)
            lease = self._lease
            if lease is None:
                self._lease_lost.set()
                return
            try:
                renewed = await asyncio.to_thread(
                    self._lease_coordinator.renew, lease
                )
            except Exception as exc:
                self._last_error = type(exc).__name__
                renewed = None
            if renewed is None:
                self._lease_state = "LOST"
                self._lease_lost.set()
                # Interrupt any in-flight provider await; the fenced store write
                # remains the final authority if a worker thread is already running.
                if self._task is not None and not self._task.done():
                    self._task.cancel()
                return
            self._lease = renewed

    async def run_once(self) -> dict[str, Any]:
        self._running = True
        self._cycles += 1
        self._last_cycle_at = datetime.now(timezone.utc).isoformat()
        results: list[dict[str, Any]] = []
        try:
            for job in self.jobs:
                if self._lease_lost is not None and self._lease_lost.is_set():
                    break
                market, symbol, interval = job["market"], job["symbol"], job["interval"]
                try:
                    latest = await asyncio.to_thread(
                        self.store.latest_open_time, market, symbol, interval
                    )
                    # Re-fetch the newest stored candle so a still-forming exchange
                    # candle is updated on the next cycle rather than frozen early.
                    start_time_ms = latest if latest is not None else None
                    limit = 1500 if market != "SPOT" else 1000
                    if start_time_ms is None:
                        limit = min(limit, self.initial_limit)
                    provider = (
                        self.spot_provider_factory()
                        if market == "SPOT"
                        else self.futures_provider_factory(market)
                    )
                    rows = await provider.klines(
                        symbol,
                        interval,
                        limit=limit,
                        start_time_ms=start_time_ms,
                        end_time_ms=int(datetime.now(timezone.utc).timestamp() * 1000),
                    )
                    if not rows:
                        results.append({
                            **job, "status": "NO_NEW_DATA", "received_count": 0,
                            "cursor_open_time_ms": latest,
                        })
                        continue
                    if self._lease_lost is not None and self._lease_lost.is_set():
                        break
                    saved = await asyncio.to_thread(
                        self.store.save_klines, market, symbol, interval, rows,
                        "Binance public REST API (scheduled collector)",
                        lease=self._lease,
                    )
                    results.append({
                        **job, "status": "COMPLETED", "received_count": len(rows),
                        "first_open_time_ms": saved["first_open_time_ms"],
                        "last_open_time_ms": saved["last_open_time_ms"],
                        "total_stored_count": saved["total_stored_count"],
                    })
                    self._successes += 1
                    self._last_success_at = datetime.now(timezone.utc).isoformat()
                except asyncio.CancelledError:
                    raise
                except CollectorLeaseLostError as exc:
                    self._lease_state = "LOST"
                    if self._lease_lost is not None:
                        self._lease_lost.set()
                    self._last_error = type(exc).__name__
                    self._failures += 1
                    results.append({
                        **job, "status": "FAILED", "error_type": type(exc).__name__,
                    })
                    break
                except Exception as exc:
                    self._failures += 1
                    self._last_error = type(exc).__name__
                    results.append({
                        **job, "status": "FAILED", "error_type": type(exc).__name__,
                    })
            self._last_results = results
            failed = any(item["status"] == "FAILED" for item in results)
            status = (
                "LEASE_LOST" if self._lease_lost is not None and self._lease_lost.is_set()
                else "INCOMPLETE" if failed
                else "IDLE" if not self.jobs
                else "COMPLETED"
            )
            return {
                "status": status,
                "cycle": self._cycles,
                "job_count": len(self.jobs),
                "results": results,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
        finally:
            self._running = False

    def status(self) -> dict[str, Any]:
        return {
            "status": "RUNNING" if self._task is not None and not self._task.done() else "STOPPED",
            "enabled": True,
            "running_cycle": self._running,
            "poll_seconds": self.poll_seconds,
            "job_count": len(self.jobs),
            "jobs": self.jobs,
            "cycles": self._cycles,
            "successful_jobs": self._successes,
            "failed_jobs": self._failures,
            "lease_state": self._lease_state,
            "lease_name": (
                self._lease_coordinator.lease_name
                if self._lease_coordinator is not None else None
            ),
            "lease_fencing_token": (
                self._lease.fencing_token if self._lease is not None else None
            ),
            "last_cycle_at": self._last_cycle_at,
            "last_success_at": self._last_success_at,
            "last_error_type": self._last_error,
            "last_results": self._last_results,
            "warning": (
                "PostgreSQL lease fencing covers scheduled and manual historical-kline collection; "
                "other collector families use their own coordination leases."
                if self._lease_coordinator is not None else
                "The collector only runs while this application process is alive. "
                "Use persistent storage and one collector process per database."
            ),
        }
