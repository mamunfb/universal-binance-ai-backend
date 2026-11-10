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
