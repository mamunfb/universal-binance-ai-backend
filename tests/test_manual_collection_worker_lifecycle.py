import asyncio
import threading
from types import SimpleNamespace

import pytest

from app import main


@pytest.mark.asyncio
async def test_manual_thread_worker_drains_after_repeated_cancellation():
    started = threading.Event()
    finish = threading.Event()

    def blocking_worker():
        started.set()
        if not finish.wait(timeout=3):
            raise TimeoutError("test worker was not released")
        return "completed"

    task = asyncio.create_task(main._run_thread_worker(blocking_worker))
    assert await asyncio.to_thread(started.wait, 2)
    task.cancel()
    await asyncio.sleep(0.05)
    task.cancel()
    await asyncio.sleep(0.05)
    assert not task.done()

    finish.set()
    result = await asyncio.gather(task, return_exceptions=True)

    assert result == [("completed", True)]


@pytest.mark.asyncio
async def test_manual_derivatives_acquire_reaps_lease_after_repeated_cancellation(monkeypatch):
    started = threading.Event()
    finish = threading.Event()
    lease = SimpleNamespace(fencing_token=501)
    released = []

    class BlockingLeaseManager:
        def __init__(self, *_args, **_kwargs):
            pass

        def acquire(self):
            started.set()
            if not finish.wait(timeout=3):
                raise TimeoutError("test acquire was not released")
            return lease

        def release(self, current):
            released.append(current)
            return True

    monkeypatch.setattr(main.settings, "database_url", "postgresql://example/test")
    monkeypatch.setattr(main, "PostgresCollectorLease", BlockingLeaseManager)

    task = asyncio.create_task(main._acquire_manual_derivatives_lease())
    assert await asyncio.to_thread(started.wait, 2)
    task.cancel()
    await asyncio.sleep(0.05)
    task.cancel()
    await asyncio.sleep(0.05)
    assert not task.done()
    assert released == []

    finish.set()
    result = await asyncio.gather(task, return_exceptions=True)

    assert isinstance(result[0], asyncio.CancelledError)
    assert released == [lease]


@pytest.mark.asyncio
async def test_manual_derivatives_release_finishes_before_cancellation_propagates():
    started = threading.Event()
    finish = threading.Event()
    lease = SimpleNamespace(fencing_token=601)
    released = []

    class BlockingLeaseManager:
        def release(self, current):
            assert current is lease
            started.set()
            if not finish.wait(timeout=3):
                raise TimeoutError("test release was not released")
            released.append(current)
            return True

    manager = BlockingLeaseManager()
    task = asyncio.create_task(main._release_manual_derivatives_lease(manager, lease))
    assert await asyncio.to_thread(started.wait, 2)
    task.cancel()
    await asyncio.sleep(0.05)
    task.cancel()
    await asyncio.sleep(0.05)
    assert not task.done()
    assert released == []

    finish.set()
    result = await asyncio.gather(task, return_exceptions=True)

    assert isinstance(result[0], asyncio.CancelledError)
    assert released == [lease]


@pytest.mark.asyncio
async def test_manual_ratio_releases_latest_lease_after_cancelled_renewal(monkeypatch):
    renew_started = threading.Event()
    finish_renew = threading.Event()
    initial_lease = SimpleNamespace(fencing_token=701)
    renewed_lease = SimpleNamespace(fencing_token=702)
    released = []

    class BlockingLeaseManager:
        def __init__(self, *_args, **_kwargs):
            pass

        def acquire(self):
            return initial_lease

        def renew(self, current):
            assert current is initial_lease
            renew_started.set()
            if not finish_renew.wait(timeout=3):
                raise TimeoutError("test renewal was not released")
            return renewed_lease

        def release(self, current):
            released.append(current)
            return True

    class FakeProvider:
        async def global_long_short_ratio(self, *_args, **_kwargs):
            return [{"symbol": "BTCUSDT", "timestamp": 1700000000000}]

    monkeypatch.setattr(main.settings, "database_url", "postgresql://example/test")
    monkeypatch.setattr(main, "PostgresCollectorLease", BlockingLeaseManager)
    monkeypatch.setattr(main, "get_futures_provider", lambda _market: FakeProvider())

    task = asyncio.create_task(
        main.collect_derivatives_ratio_history("GLOBAL_LONG_SHORT", "BTCUSDT", "1h", 10)
    )
    assert await asyncio.to_thread(renew_started.wait, 2)
    task.cancel()
    await asyncio.sleep(0.05)
    task.cancel()
    await asyncio.sleep(0.05)
    assert not task.done()
    assert released == []

    finish_renew.set()
    result = await asyncio.gather(task, return_exceptions=True)

    assert isinstance(result[0], asyncio.CancelledError)
    assert released == [renewed_lease]


@pytest.mark.asyncio
async def test_manual_kline_drains_write_before_releasing_renewed_lease(monkeypatch):
    save_started = threading.Event()
    finish_save = threading.Event()
    initial_lease = SimpleNamespace(fencing_token=801)
    renewed_lease = SimpleNamespace(fencing_token=802)
    released = []
    saved_leases = []

    class FakeLeaseManager:
        def __init__(self, *_args, **_kwargs):
            pass

        def acquire(self):
            return initial_lease

        def renew(self, current):
            assert current is initial_lease
            return renewed_lease

        def release(self, current):
            released.append(current)
            return True

    class FakeProvider:
        async def klines(self, *_args, **_kwargs):
            return [[1700000000000, "1", "2", "0.5", "1.5", "10",
                     1700000059999, "15", 3, "4", "6", "0"]]

    def blocking_save(*_args, lease=None, **_kwargs):
        saved_leases.append(lease)
        save_started.set()
        if not finish_save.wait(timeout=3):
            raise TimeoutError("test kline write was not released")
        return {"status": "COMPLETED", "stored_count": 1}

    monkeypatch.setattr(main.settings, "database_url", "postgresql://example/test")
    monkeypatch.setattr(main.settings, "historical_kline_database_url", "")
    monkeypatch.setattr(main, "PostgresCollectorLease", FakeLeaseManager)
    monkeypatch.setattr(main, "get_spot_provider", lambda: FakeProvider())
    monkeypatch.setattr(main.historical_kline_store, "save_klines", blocking_save)

    task = asyncio.create_task(
        main.collect_historical_klines("SPOT", "BTCUSDT", "1m", 10)
    )
    assert await asyncio.to_thread(save_started.wait, 2)
    task.cancel()
    await asyncio.sleep(0.05)
    task.cancel()
    await asyncio.sleep(0.05)
    assert not task.done()
    assert released == []

    finish_save.set()
    result = await asyncio.gather(task, return_exceptions=True)

    assert isinstance(result[0], asyncio.CancelledError)
    assert saved_leases == [renewed_lease]
    assert released == [renewed_lease]
