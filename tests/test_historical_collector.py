import asyncio
import pytest

from app.services.historical_collector import (
    HistoricalKlineCollector,
    parse_collector_jobs,
)
from app.services.historical_klines import HistoricalKlineStore


def candle(open_time, close="101"):
    return [
        open_time, "100", "105", "99", close, "10",
        open_time + 59_999, "1000", 25, "4", "400", "0",
    ]


class FakeProvider:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    async def klines(self, symbol, interval, limit=500, start_time_ms=None, end_time_ms=None):
        self.calls.append({
            "symbol": symbol, "interval": interval, "limit": limit,
            "start_time_ms": start_time_ms, "end_time_ms": end_time_ms,
        })
        return self.rows


def test_parse_jobs_validates_and_deduplicates():
    jobs = parse_collector_jobs(
        '[{"market":"spot","symbol":"btcusdt","interval":"1m"}]'
    )
    assert jobs == [{"market": "SPOT", "symbol": "BTCUSDT", "interval": "1m"}]
    with pytest.raises(ValueError, match="Duplicate"):
        parse_collector_jobs(
            '[{"market":"SPOT","symbol":"BTCUSDT","interval":"1m"},'
            '{"market":"SPOT","symbol":"BTCUSDT","interval":"1m"}]'
        )
    with pytest.raises(ValueError):
        parse_collector_jobs('[{"market":"BAD","symbol":"BTCUSDT","interval":"1m"}]')


def test_collector_initializes_and_resumes_with_overlap(tmp_path):
    db = str(tmp_path / "history.sqlite3")
    store = HistoricalKlineStore(db)
    start = 1_700_000_040_000
    provider = FakeProvider([candle(start)])
    collector = HistoricalKlineCollector(
        store=store,
        spot_provider_factory=lambda: provider,
        futures_provider_factory=lambda _market: provider,
        jobs_json='[{"market":"SPOT","symbol":"BTCUSDT","interval":"1m"}]',
        poll_seconds=10,
        initial_limit=50,
    )

    first = asyncio.run(collector.run_once())
    assert first["status"] == "COMPLETED"
    assert provider.calls[0]["start_time_ms"] is None
    assert provider.calls[0]["limit"] == 50
    assert store.history("SPOT", "BTCUSDT", "1m")["returned_count"] == 1

    provider.rows = [candle(start, close="102"), candle(start + 60_000)]
    second = asyncio.run(collector.run_once())
    assert second["status"] == "COMPLETED"
    assert provider.calls[1]["start_time_ms"] == start
    history = store.history("SPOT", "BTCUSDT", "1m")
    assert history["returned_count"] == 2
    assert history["candles"][0]["close"] == 102.0
    assert collector.status()["successful_jobs"] == 2


def test_collector_records_job_failure_and_continues(tmp_path):
    db = str(tmp_path / "history.sqlite3")
    store = HistoricalKlineStore(db)

    class Broken:
        async def klines(self, *args, **kwargs):
            raise RuntimeError("provider secret")

    collector = HistoricalKlineCollector(
        store=store,
        spot_provider_factory=Broken,
        futures_provider_factory=lambda _market: Broken(),
        jobs_json='[{"market":"SPOT","symbol":"BTCUSDT","interval":"1m"}]',
        poll_seconds=10,
        initial_limit=10,
    )
    result = asyncio.run(collector.run_once())
    assert result["status"] == "INCOMPLETE"
    assert result["results"][0]["status"] == "FAILED"
    assert result["results"][0]["error_type"] == "RuntimeError"
    assert "provider secret" not in str(result)


def test_collector_cancellation_waits_for_inflight_database_write(tmp_path):
    import threading
    import time

    db = str(tmp_path / "history.sqlite3")
    store = HistoricalKlineStore(db)
    started = threading.Event()
    release = threading.Event()
    original_save = store.save_klines

    def blocking_save(*args, **kwargs):
        started.set()
        if not release.wait(timeout=3):
            raise TimeoutError("test write release timed out")
        return original_save(*args, **kwargs)

    store.save_klines = blocking_save
    start = 1_700_000_040_000
    provider = FakeProvider([candle(start)])
    collector = HistoricalKlineCollector(
        store=store,
        spot_provider_factory=lambda: provider,
        futures_provider_factory=lambda _market: provider,
        jobs_json='[{"market":"SPOT","symbol":"BTCUSDT","interval":"1m"}]',
        poll_seconds=10,
        initial_limit=10,
    )

    async def scenario():
        task = asyncio.create_task(collector.run_once())
        try:
            assert await asyncio.to_thread(started.wait, 1)
            task.cancel()
            await asyncio.sleep(0.05)
            assert not task.done(), "cancellation must wait for the DB worker"
        finally:
            release.set()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())
    store.save_klines = original_save
    assert store.history("SPOT", "BTCUSDT", "1m")["returned_count"] == 1

def test_collector_propagates_request_observation_token_to_store(tmp_path):
    store = HistoricalKlineStore(str(tmp_path / "history.sqlite3"))
    captured = {}
    original_save = store.save_klines

    def capture_save(*args, **kwargs):
        captured.update(kwargs)
        return original_save(*args, **kwargs)

    store.save_klines = capture_save
    start = 1_700_000_040_000
    provider = FakeProvider([candle(start)])
    collector = HistoricalKlineCollector(
        store=store,
        spot_provider_factory=lambda: provider,
        futures_provider_factory=lambda _market: provider,
        jobs_json='[{"market":"SPOT","symbol":"BTCUSDT","interval":"1m"}]',
        poll_seconds=10,
        initial_limit=10,
    )

    result = asyncio.run(collector.run_once())

    assert result["status"] == "COMPLETED"
    assert isinstance(captured["observation_started_at_ns"], int)
    assert captured["observation_started_at_ns"] > 0
    saved = store.history("SPOT", "BTCUSDT", "1m")
    assert saved["candles"][0]["observation_started_at_ns"] == captured["observation_started_at_ns"]
