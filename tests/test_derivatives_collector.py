import asyncio
from types import SimpleNamespace

import pytest

from app.services.collector_lease import CollectorLeaseLostError

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
async def test_collector_runs_store_reads_and_writes_off_event_loop(tmp_path, monkeypatch):
    import threading

    loop_thread = threading.get_ident()
    observed = []
    funding = FundingRateStore(str(tmp_path / "funding.sqlite3"))
    oi = OpenInterestStore(str(tmp_path / "oi.sqlite3"))

    for store in (funding, oi):
        for method_name in ("history", "save"):
            original = getattr(store, method_name)

            def wrapped(*args, _original=original, _name=method_name, **kwargs):
                observed.append((_name, threading.get_ident()))
                return _original(*args, **kwargs)

            monkeypatch.setattr(store, method_name, wrapped)

    collector = DerivativesHistoryCollector(
        funding, oi, lambda market: FakeProvider(),
        '[{"type":"FUNDING_RATE","symbol":"BTCUSDT"},'
        '{"type":"OPEN_INTEREST","symbol":"BTCUSDT","period":"1h"}]',
        poll_seconds=30,
    )

    result = await collector.run_once()

    assert result["successful_jobs"] == 2
    assert {name for name, _ in observed} == {"history", "save"}
    assert len(observed) == 4
    assert all(thread_id != loop_thread for _, thread_id in observed)



class LeaseAwareFundingStore:
    def __init__(self, reject_write=False):
        self.saved_leases = []
        self.reject_write = reject_write

    def history(self, market, symbol, limit=1):
        return {"events": []}

    def save(self, market, symbol, rows, source, lease=None):
        self.saved_leases.append(lease)
        if self.reject_write:
            raise CollectorLeaseLostError("stale derivatives lease")
        return {"status": "COMPLETED", "stored_count": len(rows)}


class LeaseAwareOpenInterestStore:
    def __init__(self):
        self.saved_leases = []

    def history(self, market, symbol, period, limit=1):
        return {"records": []}

    def save(self, market, symbol, period, rows, source, lease=None):
        self.saved_leases.append(lease)
        return {"status": "COMPLETED", "stored_count": len(rows)}


class FakeLeaseCoordinator:
    ttl_seconds = 5

    def __init__(self, database_url, lease_name, ttl_seconds=30):
        self.lease_name = lease_name
        self.lease = SimpleNamespace(fencing_token=1)
        self.acquired = 0
        self.renewed = 0
        self.released = 0
        self.lose_on_renew = False
        self.unavailable = False

    def acquire(self):
        self.acquired += 1
        return None if self.unavailable else self.lease

    def renew(self, lease):
        self.renewed += 1
        return None if self.lose_on_renew else lease

    def release(self, lease):
        self.released += 1
        return True


@pytest.mark.asyncio
async def test_runtime_derivatives_collector_acquires_fences_and_releases_lease(monkeypatch):
    import app.services.derivatives_collector as module

    coordinator = FakeLeaseCoordinator("postgresql://localhost/test", "derivatives")
    monkeypatch.setattr(module, "PostgresCollectorLease", lambda *args, **kwargs: coordinator)
    funding = LeaseAwareFundingStore()
    oi = LeaseAwareOpenInterestStore()
    provider = FakeProvider()
    collector = DerivativesHistoryCollector(
        funding, oi, lambda market: provider,
        '[{"type":"FUNDING_RATE","symbol":"BTCUSDT"},'
        '{"type":"OPEN_INTEREST","symbol":"BTCUSDT","period":"1h"}]',
        poll_seconds=10,
        lease_database_url="postgresql://localhost/test",
    )

    collector.start()
    for _ in range(100):
        if funding.saved_leases and oi.saved_leases:
            break
        await asyncio.sleep(0.01)
    await collector.stop()

    assert coordinator.acquired == 1
    assert funding.saved_leases == [coordinator.lease]
    assert oi.saved_leases == [coordinator.lease]
    assert coordinator.released == 1
    assert collector.status()["lease_state"] == "RELEASED"


@pytest.mark.asyncio
async def test_runtime_derivatives_collector_waits_when_another_owner_holds_lease(monkeypatch):
    import app.services.derivatives_collector as module

    coordinator = FakeLeaseCoordinator("postgresql://localhost/test", "derivatives")
    coordinator.unavailable = True
    monkeypatch.setattr(module, "PostgresCollectorLease", lambda *args, **kwargs: coordinator)
    funding = LeaseAwareFundingStore()
    oi = LeaseAwareOpenInterestStore()
    provider = FakeProvider()
    collector = DerivativesHistoryCollector(
        funding, oi, lambda market: provider,
        '[{"type":"FUNDING_RATE","symbol":"BTCUSDT"}]',
        poll_seconds=10,
        lease_database_url="postgresql://localhost/test",
    )

    collector.start()
    await asyncio.sleep(0.05)
    await collector.stop()

    assert provider.funding_calls == []
    assert funding.saved_leases == []
    assert collector.status()["lease_state"] == "HELD_BY_OTHER"


@pytest.mark.asyncio
async def test_runtime_derivatives_collector_stops_after_lease_renewal_loss(monkeypatch):
    import app.services.derivatives_collector as module

    coordinator = FakeLeaseCoordinator("postgresql://localhost/test", "derivatives")
    coordinator.lose_on_renew = True
    monkeypatch.setattr(module, "PostgresCollectorLease", lambda *args, **kwargs: coordinator)
    funding = LeaseAwareFundingStore()
    oi = LeaseAwareOpenInterestStore()
    provider = FakeProvider()
    collector = DerivativesHistoryCollector(
        funding, oi, lambda market: provider,
        '[{"type":"FUNDING_RATE","symbol":"BTCUSDT"}]',
        poll_seconds=10,
        lease_database_url="postgresql://localhost/test",
    )

    collector.start()
    for _ in range(300):
        if collector.status()["lease_state"] == "LOST":
            break
        await asyncio.sleep(0.01)
    await collector.stop()

    assert coordinator.renewed == 1
    assert len(provider.funding_calls) == 1
    assert len(funding.saved_leases) == 1
    assert coordinator.released == 0
    assert collector.status()["status"] == "LEASE_LOST"


@pytest.mark.asyncio
async def test_runtime_derivatives_collector_stops_on_fenced_write_rejection(monkeypatch):
    import app.services.derivatives_collector as module

    coordinator = FakeLeaseCoordinator("postgresql://localhost/test", "derivatives")
    monkeypatch.setattr(module, "PostgresCollectorLease", lambda *args, **kwargs: coordinator)
    funding = LeaseAwareFundingStore(reject_write=True)
    oi = LeaseAwareOpenInterestStore()
    provider = FakeProvider()
    collector = DerivativesHistoryCollector(
        funding, oi, lambda market: provider,
        '[{"type":"FUNDING_RATE","symbol":"BTCUSDT"},'
        '{"type":"OPEN_INTEREST","symbol":"BTCUSDT","period":"1h"}]',
        poll_seconds=10,
        lease_database_url="postgresql://localhost/test",
    )

    collector.start()
    for _ in range(100):
        if collector.status()["lease_state"] == "LOST":
            break
        await asyncio.sleep(0.01)
    await collector.stop()

    assert coordinator.acquired == 1
    assert len(provider.funding_calls) == 1
    assert provider.oi_calls == []
    assert len(funding.saved_leases) == 1
    assert coordinator.released == 0
    assert collector.status()["status"] == "LEASE_LOST"



@pytest.mark.asyncio
async def test_run_once_requires_lease_when_postgres_lease_mode_is_configured(monkeypatch):
    import app.services.derivatives_collector as module

    coordinator = FakeLeaseCoordinator("postgresql://localhost/test", "derivatives")
    monkeypatch.setattr(module, "PostgresCollectorLease", lambda *args, **kwargs: coordinator)
    collector = DerivativesHistoryCollector(
        LeaseAwareFundingStore(), LeaseAwareOpenInterestStore(),
        lambda market: FakeProvider(),
        '[{"type":"FUNDING_RATE","symbol":"BTCUSDT"}]',
        lease_database_url="postgresql://localhost/test",
    )
    with pytest.raises(CollectorLeaseLostError, match="currently owned"):
        await collector.run_once()


@pytest.mark.asyncio
async def test_runtime_derivatives_collector_cancels_inflight_provider_and_releases_lease(monkeypatch):
    import app.services.derivatives_collector as module

    started = asyncio.Event()
    cancelled = asyncio.Event()

    class BlockingProvider(FakeProvider):
        async def funding_rate(self, *args, **kwargs):
            started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled.set()
                raise

    coordinator = FakeLeaseCoordinator("postgresql://localhost/test", "derivatives")
    monkeypatch.setattr(module, "PostgresCollectorLease", lambda *args, **kwargs: coordinator)
    provider = BlockingProvider()
    collector = DerivativesHistoryCollector(
        LeaseAwareFundingStore(), LeaseAwareOpenInterestStore(),
        lambda market: provider,
        '[{"type":"FUNDING_RATE","symbol":"BTCUSDT"}]',
        poll_seconds=10,
        lease_database_url="postgresql://localhost/test",
    )

    collector.start()
    await asyncio.wait_for(started.wait(), timeout=1)
    await asyncio.wait_for(collector.stop(), timeout=1)

    assert cancelled.is_set()
    assert coordinator.acquired == 1
    assert coordinator.released == 1
    assert collector.status()["status"] == "STOPPED"
    assert collector.status()["lease_state"] == "RELEASED"
