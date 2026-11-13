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

def test_historical_collector_status_reports_stopped_and_degraded(tmp_path):
    collector = HistoricalKlineCollector(
        store=HistoricalKlineStore(str(tmp_path / "status.sqlite3")),
        spot_provider_factory=lambda: None,
        futures_provider_factory=lambda _market: None,
        jobs_json="[]",
    )
    assert collector.status()["status"] == "STOPPED"
    assert collector.status()["task_active"] is False

    class ActiveTask:
        def done(self):
            return False

    collector._task = ActiveTask()
    collector._last_error = "RuntimeError"
    status = collector.status()
    assert status["status"] == "DEGRADED"
    assert status["task_active"] is True


def test_historical_collector_recovers_status_after_successful_cycle(tmp_path):
    class EmptyProvider:
        async def klines(self, *args, **kwargs):
            return []

    collector = HistoricalKlineCollector(
        store=HistoricalKlineStore(str(tmp_path / "recovery.sqlite3")),
        spot_provider_factory=EmptyProvider,
        futures_provider_factory=lambda _market: EmptyProvider(),
        jobs_json='[{"market":"SPOT","symbol":"BTCUSDT","interval":"1m"}]',
    )

    class ActiveTask:
        def done(self):
            return False

    collector._task = ActiveTask()
    assert collector.status()["status"] == "STARTING"
    collector._last_error = "RuntimeError"
    collector._last_cycle_degraded = True
    result = asyncio.run(collector.run_once())

    assert result["status"] == "COMPLETED"
    assert collector.status()["status"] == "RUNNING"
    assert collector.status()["last_error_type"] == "RuntimeError"
