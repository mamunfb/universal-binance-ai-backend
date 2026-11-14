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



class LeaseAwareStore:
    def __init__(self):
        self.saved_leases = []

    def latest_open_time(self, market, symbol, interval):
        return None

    def save_klines(self, market, symbol, interval, rows, source, lease=None):
        self.saved_leases.append(lease)
        return {
            "first_open_time_ms": rows[0][0],
            "last_open_time_ms": rows[-1][0],
            "total_stored_count": len(rows),
        }


class FakeLeaseCoordinator:
    ttl_seconds = 5

    def __init__(self, database_url, lease_name, ttl_seconds=30):
        self.acquired = 0
        self.renewed = 0
        self.released = 0
        self.lease = object()
        self.lose_on_renew = False

    def acquire(self):
        self.acquired += 1
        return self.lease

    def renew(self, lease):
        self.renewed += 1
        return None if self.lose_on_renew else lease

    def release(self, lease):
        self.released += 1
        return True


def test_runtime_collector_acquires_passes_and_releases_lease(monkeypatch):
    import app.services.historical_collector as module

    coordinator = FakeLeaseCoordinator("postgresql://localhost/test", "historical")
    monkeypatch.setattr(module, "PostgresCollectorLease", lambda *args, **kwargs: coordinator)
    store = LeaseAwareStore()
    provider = FakeProvider([candle(1_700_000_040_000)])
    collector = HistoricalKlineCollector(
        store=store,
        spot_provider_factory=lambda: provider,
        futures_provider_factory=lambda _market: provider,
        jobs_json='[{"market":"SPOT","symbol":"BTCUSDT","interval":"1m"}]',
        poll_seconds=10,
        lease_database_url="postgresql://localhost/test",
    )

    async def exercise():
        collector.start()
        for _ in range(50):
            if store.saved_leases:
                break
            await asyncio.sleep(0.01)
        await collector.stop()

    asyncio.run(exercise())
    assert coordinator.acquired == 1
    assert store.saved_leases == [coordinator.lease]
    assert coordinator.released == 1
    assert collector.status()["lease_state"] == "RELEASED"


def test_runtime_collector_does_not_collect_when_another_owner_holds_lease(monkeypatch):
    import app.services.historical_collector as module

    coordinator = FakeLeaseCoordinator("postgresql://localhost/test", "historical")
    coordinator.acquire = lambda: None
    monkeypatch.setattr(module, "PostgresCollectorLease", lambda *args, **kwargs: coordinator)
    store = LeaseAwareStore()
    provider = FakeProvider([candle(1_700_000_040_000)])
    collector = HistoricalKlineCollector(
        store=store,
        spot_provider_factory=lambda: provider,
        futures_provider_factory=lambda _market: provider,
        jobs_json='[{"market":"SPOT","symbol":"BTCUSDT","interval":"1m"}]',
        poll_seconds=10,
        lease_database_url="postgresql://localhost/test",
    )

    async def exercise():
        collector.start()
        await asyncio.sleep(0.05)
        await collector.stop()

    asyncio.run(exercise())
    assert provider.calls == []
    assert store.saved_leases == []
    assert collector.status()["lease_state"] == "HELD_BY_OTHER"


def test_runtime_collector_stops_after_lease_renewal_is_lost(monkeypatch):
    import app.services.historical_collector as module

    coordinator = FakeLeaseCoordinator("postgresql://localhost/test", "historical")
    coordinator.lose_on_renew = True
    monkeypatch.setattr(module, "PostgresCollectorLease", lambda *args, **kwargs: coordinator)
    store = LeaseAwareStore()
    provider = FakeProvider([candle(1_700_000_040_000)])
    collector = HistoricalKlineCollector(
        store=store,
        spot_provider_factory=lambda: provider,
        futures_provider_factory=lambda _market: provider,
        jobs_json='[{"market":"SPOT","symbol":"BTCUSDT","interval":"1m"}]',
        poll_seconds=10,
        lease_database_url="postgresql://localhost/test",
    )

    async def exercise():
        collector.start()
        for _ in range(300):
            if collector.status()["lease_state"] == "LOST":
                break
            await asyncio.sleep(0.01)
        await asyncio.sleep(0.05)
        await collector.stop()

    asyncio.run(exercise())
    assert coordinator.renewed == 1
    assert provider.calls
    assert len(store.saved_leases) == 1
    assert coordinator.released == 0
    assert collector.status()["lease_state"] == "LOST"
