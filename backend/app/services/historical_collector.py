from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any, Callable

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
        self._task: asyncio.Task | None = None
        self._running = False
        self._last_cycle_at: str | None = None
        self._last_success_at: str | None = None
        self._last_error: str | None = None
        self._last_cycle_degraded = False
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
        while True:
            try:
                await self.run_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._last_error = type(exc).__name__
                self._last_cycle_degraded = True
            await asyncio.sleep(self.poll_seconds)

    async def run_once(self) -> dict[str, Any]:
        self._running = True
        self._cycles += 1
        self._last_cycle_at = datetime.now(timezone.utc).isoformat()
        results: list[dict[str, Any]] = []
        try:
            for job in self.jobs:
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
                    saved = await asyncio.to_thread(
                        self.store.save_klines, market, symbol, interval, rows,
                        "Binance public REST API (scheduled collector)",
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
                except Exception as exc:
                    self._failures += 1
                    self._last_error = type(exc).__name__
                    results.append({
                        **job, "status": "FAILED", "error_type": type(exc).__name__,
                    })
            self._last_results = results
            failed = any(item["status"] == "FAILED" for item in results)
            self._last_cycle_degraded = failed
            status = "INCOMPLETE" if failed else ("IDLE" if not self.jobs else "COMPLETED")
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
        task_active = self._task is not None and not self._task.done()
        if not task_active:
            lifecycle_status = "STOPPED"
        elif self._cycles == 0:
            lifecycle_status = "STARTING"
        elif self._last_cycle_degraded:
            lifecycle_status = "DEGRADED"
        else:
            lifecycle_status = "RUNNING"
        return {
            "status": lifecycle_status,
            "enabled": True,
            "task_active": task_active,
            "running_cycle": self._running,
            "poll_seconds": self.poll_seconds,
            "job_count": len(self.jobs),
            "jobs": self.jobs,
            "cycles": self._cycles,
            "successful_jobs": self._successes,
            "failed_jobs": self._failures,
            "last_cycle_at": self._last_cycle_at,
            "last_success_at": self._last_success_at,
            "last_error_type": self._last_error,
            "last_results": self._last_results,
            "warning": "The collector only runs while this application process is alive. Use persistent storage and one collector process per database.",
        }
