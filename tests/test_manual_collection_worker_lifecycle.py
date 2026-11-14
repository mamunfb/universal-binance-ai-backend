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
