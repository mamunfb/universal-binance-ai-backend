import pytest

from app.services.derivatives_collector import (
    DerivativesHistoryCollector, parse_derivatives_jobs,
)
from app.services.funding_rates import FundingRateStore
from app.services.open_interest import OpenInterestStore


def funding_event(ts):
    return {"symbol": "BTCUSDT", "fundingTime": ts,
            "fundingRate": "0.0001", "markPrice": "37000"}


def oi_record(ts):
    return {"symbol": "BTCUSDT", "timestamp": ts,
            "sumOpenInterest": "10", "sumOpenInterestValue": "1000"}


def test_parse_derivatives_jobs_validates_and_normalizes():
    jobs = parse_derivatives_jobs(
        '[{"type":"funding_rate","symbol":"btcusdt"},'
        '{"type":"open_interest","symbol":"ethusdt","period":"15m"}]'
    )
    assert jobs == [
        {"type": "FUNDING_RATE", "symbol": "BTCUSDT", "period": ""},
        {"type": "OPEN_INTEREST", "symbol": "ETHUSDT", "period": "15m"},
    ]


@pytest.mark.parametrize("raw", [
    "not-json", "{}", '[{"type":"UNKNOWN","symbol":"BTCUSDT"}]',
    '[{"type":"OPEN_INTEREST","symbol":"BTCUSDT","period":"2w"}]',
    '[{"type":"FUNDING_RATE","symbol":"BTCUSDT"},{"type":"FUNDING_RATE","symbol":"btcusdt"}]',
])
def test_parse_derivatives_jobs_rejects_invalid_config(raw):
    with pytest.raises(ValueError):
        parse_derivatives_jobs(raw)


class FakeProvider:
    def __init__(self):
        self.funding_calls = []
        self.oi_calls = []

    async def funding_rate(self, symbol, limit=1000, start_time_ms=None, end_time_ms=None):
        self.funding_calls.append((symbol, limit, start_time_ms))
        start = start_time_ms or 1700000000000
        return [funding_event(start), funding_event(start + 8 * 60 * 60 * 1000)]

    async def open_interest_history(
        self, symbol, period="1h", limit=500, start_time_ms=None, end_time_ms=None
    ):
        self.oi_calls.append((symbol, period, limit, start_time_ms))
        start = start_time_ms or 1700000000000
        return [oi_record(start), oi_record(start + 3600000)]


@pytest.mark.asyncio
async def test_collector_polls_both_series_and_resumes_from_latest(tmp_path):
    funding = FundingRateStore(str(tmp_path / "funding.sqlite3"))
    oi = OpenInterestStore(str(tmp_path / "oi.sqlite3"))
    provider = FakeProvider()
    collector = DerivativesHistoryCollector(
        funding, oi, lambda market: provider,
        '[{"type":"FUNDING_RATE","symbol":"BTCUSDT"},'
        '{"type":"OPEN_INTEREST","symbol":"BTCUSDT","period":"1h"}]',
        poll_seconds=30,
    )
    first = await collector.run_once()
    assert first["successful_jobs"] == 2
    assert funding.history("USD_M", "BTCUSDT")["returned_count"] == 2
    assert oi.history("USD_M", "BTCUSDT", "1h")["returned_count"] == 2
    second = await collector.run_once()
    assert provider.funding_calls[1][2] == 1700028800000
    assert provider.oi_calls[1][3] == 1700003600000
    assert second["cycles"] == 2


@pytest.mark.asyncio
async def test_collector_records_per_job_failure_and_continues(tmp_path):
    class PartialProvider(FakeProvider):
        async def funding_rate(self, *args, **kwargs):
            raise RuntimeError("private provider details")

    provider = PartialProvider()
    collector = DerivativesHistoryCollector(
        FundingRateStore(str(tmp_path / "funding.sqlite3")),
        OpenInterestStore(str(tmp_path / "oi.sqlite3")),
        lambda market: provider,
        '[{"type":"FUNDING_RATE","symbol":"BTCUSDT"},'
        '{"type":"OPEN_INTEREST","symbol":"BTCUSDT","period":"1h"}]',
    )
    result = await collector.run_once()
    assert result["status"] == "DEGRADED"
    assert result["failed_jobs"] == 1
    assert result["successful_jobs"] == 1
    assert result["last_results"][0]["error_type"] == "RuntimeError"
    assert "private provider details" not in str(result)


def test_collector_validates_polling_and_limits(tmp_path):
    funding = FundingRateStore(str(tmp_path / "funding.sqlite3"))
    oi = OpenInterestStore(str(tmp_path / "oi.sqlite3"))
    with pytest.raises(ValueError, match="poll_seconds"):
        DerivativesHistoryCollector(funding, oi, lambda _: FakeProvider(), "[]", poll_seconds=1)


@pytest.mark.asyncio
async def test_collector_stop_cancels_inflight_provider_request(tmp_path):
    import asyncio

    started = asyncio.Event()

    class BlockingProvider(FakeProvider):
        async def funding_rate(self, *args, **kwargs):
            started.set()
            await asyncio.Event().wait()

    provider = BlockingProvider()
    collector = DerivativesHistoryCollector(
        FundingRateStore(str(tmp_path / "funding.sqlite3")),
        OpenInterestStore(str(tmp_path / "oi.sqlite3")),
        lambda market: provider,
        '[{"type":"FUNDING_RATE","symbol":"BTCUSDT"}]',
        poll_seconds=30,
    )

    collector.start()
    await asyncio.wait_for(started.wait(), timeout=1)
    await asyncio.wait_for(collector.stop(), timeout=1)

    assert collector.status()["status"] == "STOPPED"
    assert collector._task is None


@pytest.mark.asyncio
async def test_collector_retries_failed_job_on_next_cycle(tmp_path):
    class RecoveringProvider(FakeProvider):
        def __init__(self):
            super().__init__()
            self.fail_once = True

        async def funding_rate(self, *args, **kwargs):
            if self.fail_once:
                self.fail_once = False
                raise RuntimeError("temporary upstream failure")
            return await super().funding_rate(*args, **kwargs)

    provider = RecoveringProvider()
    funding = FundingRateStore(str(tmp_path / "funding.sqlite3"))
    oi = OpenInterestStore(str(tmp_path / "oi.sqlite3"))
    collector = DerivativesHistoryCollector(
        funding, oi, lambda market: provider,
        '[{"type":"FUNDING_RATE","symbol":"BTCUSDT"}]',
        poll_seconds=30,
    )

    failed = await collector.run_once()
    recovered = await collector.run_once()

    assert failed["status"] == "DEGRADED"
    assert failed["last_results"][0]["status"] == "FAILED"
    assert recovered["status"] == "RUNNING"
    assert recovered["last_results"][0]["status"] == "COMPLETED"
    assert funding.history("USD_M", "BTCUSDT")["returned_count"] == 2


@pytest.mark.asyncio
async def test_collector_cancellation_waits_for_inflight_derivative_database_write(tmp_path):
    import asyncio
    import threading

    started = threading.Event()
    release = threading.Event()

    class BlockingFundingStore:
        def history(self, *args, **kwargs):
            return {"events": []}

        def save(self, *args, **kwargs):
            started.set()
            if not release.wait(timeout=3):
                raise TimeoutError("test write release timed out")
            return {"status": "COMPLETED", "stored_count": 1}

    class EmptyOIStore:
        def history(self, *args, **kwargs):
            return {"records": []}

        def save(self, *args, **kwargs):
            return {"status": "COMPLETED"}

    provider = FakeProvider()
    collector = DerivativesHistoryCollector(
        BlockingFundingStore(), EmptyOIStore(), lambda market: provider,
        '[{"type":"FUNDING_RATE","symbol":"BTCUSDT"}]',
    )

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
