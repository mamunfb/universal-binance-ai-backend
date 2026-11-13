from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any, Callable

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
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()
        self._lock = asyncio.Lock()
        self._lease_owner_token: str | None = None
        self._status: dict[str, Any] = {
            "status": "IDLE", "enabled": True, "job_count": len(self.jobs),
            "poll_seconds": poll_seconds, "cycles": 0, "successful_jobs": 0,
            "failed_jobs": 0, "last_cycle_at": None, "last_results": [],
        }

    def start(self, lease_owner_token: str | None = None) -> None:
        self._lease_owner_token = lease_owner_token
        if self._task is None or self._task.done():
            self._stop_event.clear()
            self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        self._stop_event.set()
        task = self._task
        self._task = None
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._status["status"] = "STOPPED"

    async def _run_loop(self) -> None:
        self._status["status"] = "RUNNING"
        while not self._stop_event.is_set():
            try:
                await self.run_once()
            except Exception:
                self._status["status"] = "DEGRADED"
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self.poll_seconds)
            except asyncio.TimeoutError:
                pass
        self._status["status"] = "STOPPED"

    async def run_once(self) -> dict[str, Any]:
        async with self._lock:
            results = []
            for job in self.jobs:
                try:
                    result = await self._collect_job(job)
                    results.append(result)
                    self._status["successful_jobs"] += 1
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
                "DEGRADED" if any(x["status"] == "FAILED" for x in results) else "RUNNING"
            )
            return self.status()

    async def _collect_job(self, job: dict[str, str]) -> dict[str, Any]:
        provider = self.provider_factory("USD_M")
        symbol = job["symbol"]
        if job["type"] == "FUNDING_RATE":
            history = await asyncio.to_thread(
                self.funding_store.history, "USD_M", symbol, limit=1
            )
            latest = history["events"][-1]["funding_time_ms"] if history["events"] else None
            rows = await provider.funding_rate(
                symbol, limit=self.funding_limit, start_time_ms=latest,
            )
            if not rows:
                return {"status": "NO_NEW_DATA", **job, "received_count": 0}
            return await self._save_without_abandoning_worker(
                self.funding_store.save,
                "USD_M", symbol, rows,
                source="Binance USD-M public REST API (scheduled collector)",
            lease_owner_token=self._lease_owner_token,
            )
        period = job["period"]
        history = await asyncio.to_thread(
            self.open_interest_store.history, "USD_M", symbol, period, limit=1
        )
        latest = history["records"][-1]["timestamp_ms"] if history["records"] else None
        rows = await provider.open_interest_history(
            symbol, period=period, limit=self.open_interest_limit, start_time_ms=latest,
        )
        if not rows:
            return {"status": "NO_NEW_DATA", **job, "received_count": 0}
        return await self._save_without_abandoning_worker(
            self.open_interest_store.save,
            "USD_M", symbol, period, rows,
            source="Binance USD-M public REST API (scheduled collector)",
        lease_owner_token=self._lease_owner_token,
        )

    @staticmethod
    async def _save_without_abandoning_worker(save_callable, *args, **kwargs):
        write_task = asyncio.create_task(asyncio.to_thread(save_callable, *args, **kwargs))
        try:
            return await asyncio.shield(write_task)
        except asyncio.CancelledError:
            await asyncio.gather(write_task, return_exceptions=True)
            raise

    def status(self) -> dict[str, Any]:
        return {
            **self._status,
            "jobs": self.jobs,
            "warning": (
                "The collector runs in each application process. Use one collector process "
                "per database unless distributed coordination is configured."
            ),
        }
