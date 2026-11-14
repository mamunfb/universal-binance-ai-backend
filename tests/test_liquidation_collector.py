import asyncio
import logging

import pytest

import app.services.liquidation_collector as liquidation_module
from app.services.liquidation_collector import (
    LiquidationCollector,
    LiquidationStore,
    normalize_force_order,
)


def sample_message():
    return {
        "e": "forceOrder",
        "E": 1700000000123,
        "st": 1,
        "o": {
            "s": "BTCUSDT",
            "ps": "BTCUSDT",
            "S": "SELL",
            "o": "LIMIT",
            "q": "0.02",
            "p": "50000",
            "ap": "49900",
            "X": "FILLED",
            "l": "0.02",
            "z": "0.02",
            "T": 1700000000100,
        },
    }


def test_normalize_force_order_and_notional():
    event = normalize_force_order(sample_message())
    assert event is not None
    assert event["symbol"] == "BTCUSDT"
    assert event["side"] == "SELL"
    assert event["approx_cumulative_notional"] == 998.0
    assert event["market_type"] == 1


@pytest.mark.parametrize("field,value", [
    ("ap", "NaN"),
    ("ap", "Infinity"),
    ("q", "-1"),
    ("l", "-0.1"),
    ("z", "Infinity"),
    ("E", -1),
    ("T", -1),
    ("s", ""),
    ("S", "HOLD"),
])
def test_invalid_force_order_is_ignored(field, value):
    message = sample_message()
    if field in {"E"}:
        message[field] = value
    elif field == "T":
        message["o"][field] = value
    else:
        message["o"][field] = value
    assert normalize_force_order(message) is None


def test_boolean_timestamp_and_non_object_message_are_rejected():
    message = sample_message()
    message["E"] = True
    assert normalize_force_order(message) is None
    assert normalize_force_order([]) is None


def test_store_persists_and_filters_events(tmp_path):
    store = LiquidationStore(str(tmp_path / "events.sqlite3"))
    event = normalize_force_order(sample_message())
    assert event is not None
    store.insert(event)
    assert store.count() == 1
    rows = store.recent("btcusdt", 10)
    assert len(rows) == 1
    assert rows[0]["symbol"] == "BTCUSDT"
    assert store.recent("ETHUSDT", 10) == []


def test_liquidation_store_rejects_lease_with_sqlite_storage(tmp_path):
    store = LiquidationStore(str(tmp_path / "events.sqlite3"))
    event = normalize_force_order(sample_message())
    assert event is not None
    with pytest.raises(ValueError, match="PostgreSQL"):
        store.insert(event, lease=object())


def test_store_deduplicates_exact_repeated_payloads(tmp_path):
    store = LiquidationStore(str(tmp_path / "events.sqlite3"))
    event = normalize_force_order(sample_message())
    assert event is not None
    assert len(event["event_fingerprint"]) == 64

    store.insert(event)
    store.insert(event)

    assert store.count() == 1


def test_fingerprint_is_independent_of_json_object_key_order():
    message = sample_message()

    def reverse_mapping(value):
        if isinstance(value, dict):
            return {key: reverse_mapping(item) for key, item in reversed(list(value.items()))}
        if isinstance(value, list):
            return [reverse_mapping(item) for item in value]
        return value

    first = normalize_force_order(message)
    second = normalize_force_order(reverse_mapping(message))
    assert first is not None and second is not None
    assert first["event_fingerprint"] == second["event_fingerprint"]


def test_invalid_message_is_ignored():
    assert normalize_force_order({"e": "aggTrade"}) is None
    assert normalize_force_order({"e": "forceOrder", "o": []}) is None


def test_collector_status_and_logs_expose_only_exception_class(tmp_path, monkeypatch, caplog):
    class BrokenConnection:
        async def __aenter__(self):
            raise RuntimeError("sensitive provider detail")

        async def __aexit__(self, exc_type, exc, traceback):
            return False

    def fake_connect(*args, **kwargs):
        return BrokenConnection()

    async def cancel_retry(_delay):
        raise asyncio.CancelledError

    store = LiquidationStore(str(tmp_path / "safe-status.sqlite3"))
    collector = LiquidationCollector(store)
    monkeypatch.setattr(liquidation_module, "connect", fake_connect)
    monkeypatch.setattr(liquidation_module.asyncio, "sleep", cancel_retry)

    with caplog.at_level(logging.WARNING, logger=liquidation_module.__name__):
        with pytest.raises(asyncio.CancelledError):
            asyncio.run(collector.run())

    status = collector.status()
    assert status["last_error"] == "RuntimeError"
    assert "sensitive provider detail" not in str(status)
    assert "RuntimeError" in caplog.text
    assert "sensitive provider detail" not in caplog.text



def test_collector_status_remains_available_when_storage_count_fails():
    class UnavailableStore:
        def count(self):
            raise RuntimeError("sensitive database connection detail")

    collector = LiquidationCollector(UnavailableStore())
    status = collector.status()

    assert status["collector_enabled"] is True
    assert status["stored_event_count"] is None
    assert status["storage_status"] == "UNAVAILABLE"
    assert status["storage_error"] == "RuntimeError"
    assert "sensitive database connection detail" not in str(status)



def test_collector_retries_storage_without_reconnecting_and_redacts_error(monkeypatch):
    class FlakyStore:
        def __init__(self):
            self.attempts = 0

        def insert(self, _event):
            self.attempts += 1
            if self.attempts <= 2:
                raise RuntimeError("sensitive database connection detail")

        def count(self):
            return 1

    delays = []

    async def record_sleep(delay):
        delays.append(delay)

    monkeypatch.setattr(liquidation_module.asyncio, "sleep", record_sleep)
    store = FlakyStore()
    collector = LiquidationCollector(store)
    event = normalize_force_order(sample_message())

    asyncio.run(collector._persist_event(event))

    assert store.attempts == 3
    assert delays == [1, 2]
    assert collector.storage_error is None
    assert collector.storage_retry_count == 2
    status = collector.status()
    assert status["storage_status"] == "AVAILABLE"
    assert status["storage_error"] is None
    assert status["storage_retry_count"] == 2
    assert "sensitive database connection detail" not in str(status)


def test_collector_storage_status_reports_degraded_after_write_failure(monkeypatch):
    class BrokenStore:
        def insert(self, _event):
            raise RuntimeError("sensitive database connection detail")

        def count(self):
            return 0

    async def stop_after_first_retry(_delay):
        raise asyncio.CancelledError

    monkeypatch.setattr(liquidation_module.asyncio, "sleep", stop_after_first_retry)
    collector = LiquidationCollector(BrokenStore())
    event = normalize_force_order(sample_message())

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(collector._persist_event(event))

    status = collector.status()
    assert status["storage_status"] == "DEGRADED"
    assert status["storage_error"] == "RuntimeError"
    assert status["storage_retry_count"] == 1
    assert "sensitive database connection detail" not in str(status)


def test_liquidation_runtime_lease_acquires_and_releases_on_shutdown(monkeypatch, tmp_path):
    from types import SimpleNamespace

    class FakeLeaseCoordinator:
        lease_name = "liquidation-stream-collector"
        ttl_seconds = 30

        def __init__(self, *_args, **_kwargs):
            self.released = []

        def acquire(self):
            return SimpleNamespace(fencing_token=7)

        def renew(self, lease):
            return lease

        def release(self, lease):
            self.released.append(lease)
            return True

    monkeypatch.setattr(liquidation_module, "PostgresCollectorLease", FakeLeaseCoordinator)
    collector = LiquidationCollector(
        LiquidationStore(str(tmp_path / "lease.sqlite3")),
        lease_database_url="postgresql://test",
    )
    started = asyncio.Event()

    async def fake_stream():
        started.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(collector, "_run_stream", fake_stream)

    async def scenario():
        collector.start()
        await asyncio.wait_for(started.wait(), timeout=2)
        assert collector.status()["lease_state"] == "OWNED"
        assert collector.status()["lease_fencing_token"] == 7
        await collector.stop()

    asyncio.run(scenario())
    assert len(collector._lease_coordinator.released) == 1


def test_liquidation_runtime_waits_when_another_owner_holds_lease(monkeypatch, tmp_path):
    class FakeLeaseCoordinator:
        lease_name = "liquidation-stream-collector"
        ttl_seconds = 30

        def __init__(self, *_args, **_kwargs):
            pass

        def acquire(self):
            return None

    monkeypatch.setattr(liquidation_module, "PostgresCollectorLease", FakeLeaseCoordinator)
    collector = LiquidationCollector(
        LiquidationStore(str(tmp_path / "held.sqlite3")),
        lease_database_url="postgresql://test",
    )

    async def scenario():
        collector.start()
        for _ in range(20):
            if collector.status()["lease_state"] == "HELD_BY_OTHER":
                break
            await asyncio.sleep(0.01)
        assert collector.status()["lease_state"] == "HELD_BY_OTHER"
        assert collector.connected is False
        await collector.stop()

    asyncio.run(scenario())


def test_liquidation_fenced_write_loss_is_terminal_and_not_retried(monkeypatch, tmp_path):
    from types import SimpleNamespace
    from app.services.collector_lease import CollectorLeaseLostError

    class FakeStore:
        def insert(self, _event, lease=None):
            raise CollectorLeaseLostError("stale owner")

        def count(self):
            return 0

    collector = LiquidationCollector(FakeStore(), lease_database_url="postgresql://test")
    collector._lease = SimpleNamespace(fencing_token=9)
    event = normalize_force_order(sample_message())

    async def scenario():
        with pytest.raises(CollectorLeaseLostError):
            await collector._persist_event(event)

    asyncio.run(scenario())
    assert collector.status()["lease_state"] == "LOST"
    assert collector.storage_retry_count == 0


def test_liquidation_waits_for_inflight_insert_before_releasing_lease(monkeypatch):
    import threading
    from types import SimpleNamespace

    insert_started = threading.Event()
    finish_insert = threading.Event()
    released = []
    lease = SimpleNamespace(fencing_token=71)

    class FakeLeaseCoordinator:
        lease_name = "liquidation-stream-collector"
        ttl_seconds = 30

        def __init__(self, *_args, **_kwargs):
            pass

        def acquire(self):
            return lease

        def renew(self, current):
            return current

        def release(self, current):
            released.append(current)
            return True

    class BlockingStore:
        def insert(self, _event, lease=None):
            assert lease is not None and lease.fencing_token == 71
            insert_started.set()
            if not finish_insert.wait(timeout=3):
                raise TimeoutError("test insert was not released")

        def count(self):
            return 0

    monkeypatch.setattr(liquidation_module, "PostgresCollectorLease", FakeLeaseCoordinator)
    collector = LiquidationCollector(
        BlockingStore(), lease_database_url="postgresql://test"
    )
    event = normalize_force_order(sample_message())

    async def fake_stream():
        await collector._persist_event(event)
        await asyncio.Event().wait()

    monkeypatch.setattr(collector, "_run_stream", fake_stream)

    async def scenario():
        collector.start()
        assert await asyncio.to_thread(insert_started.wait, 2)
        task = collector.task
        task.cancel()
        await asyncio.sleep(0.05)
        task.cancel()
        await asyncio.sleep(0.05)
        assert not task.done()
        assert released == []
        finish_insert.set()
        result = await asyncio.gather(task, return_exceptions=True)
        assert isinstance(result[0], asyncio.CancelledError)
        await collector.stop()

    asyncio.run(scenario())
    assert released == [lease]
    assert collector.status()["lease_state"] == "STOPPED"


def test_liquidation_waits_for_inflight_renewal_and_releases_latest_lease(monkeypatch):
    import threading
    from types import SimpleNamespace

    renew_started = threading.Event()
    finish_renew = threading.Event()
    initial_lease = SimpleNamespace(fencing_token=81)
    renewed_lease = SimpleNamespace(fencing_token=82)
    released = []

    class FakeLeaseCoordinator:
        lease_name = "liquidation-stream-collector"
        ttl_seconds = 3

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

    monkeypatch.setattr(liquidation_module, "PostgresCollectorLease", FakeLeaseCoordinator)
    collector = LiquidationCollector(
        LiquidationStore(":memory:"), lease_database_url="postgresql://test",
        lease_ttl_seconds=3,
    )

    async def fake_stream():
        await asyncio.Event().wait()

    monkeypatch.setattr(collector, "_run_stream", fake_stream)

    async def scenario():
        collector.start()
        assert await asyncio.to_thread(renew_started.wait, 2)
        task = collector.task
        task.cancel()
        await asyncio.sleep(0.05)
        task.cancel()
        await asyncio.sleep(0.05)
        assert not task.done()
        assert released == []
        finish_renew.set()
        result = await asyncio.gather(task, return_exceptions=True)
        assert isinstance(result[0], asyncio.CancelledError)
        assert collector._lease is renewed_lease
        await collector.stop()

    asyncio.run(scenario())
    assert released == [renewed_lease]

def test_liquidation_reaps_lease_when_acquisition_is_cancelled(monkeypatch, tmp_path):
    import threading
    from types import SimpleNamespace

    acquire_started = threading.Event()
    finish_acquire = threading.Event()
    lease = SimpleNamespace(fencing_token=91)
    released = []

    class BlockingLeaseCoordinator:
        lease_name = "liquidation-stream-collector"
        ttl_seconds = 30

        def __init__(self, *_args, **_kwargs):
            pass

        def acquire(self):
            acquire_started.set()
            if not finish_acquire.wait(timeout=3):
                raise TimeoutError("test acquisition was not released")
            return lease

        def release(self, current):
            released.append(current)
            return True

    monkeypatch.setattr(liquidation_module, "PostgresCollectorLease", BlockingLeaseCoordinator)
    collector = LiquidationCollector(
        LiquidationStore(str(tmp_path / "acquire-cancel.sqlite3")),
        lease_database_url="postgresql://test",
    )

    async def scenario():
        collector.start()
        assert await asyncio.to_thread(acquire_started.wait, 2)
        task = collector.task
        task.cancel()
        await asyncio.sleep(0.05)
        task.cancel()
        await asyncio.sleep(0.05)
        assert not task.done()
        assert released == []

        finish_acquire.set()
        result = await asyncio.gather(task, return_exceptions=True)
        assert isinstance(result[0], asyncio.CancelledError)
        await collector.stop()

    asyncio.run(scenario())
    assert released == [lease]
    assert collector.status()["lease_state"] == "STOPPED"
