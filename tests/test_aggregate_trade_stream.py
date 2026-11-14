from app.services.aggregate_trade_stream import (
    AggregateTradeStore, aggregate_trade_stream_url, normalize_aggregate_trade,
)


def sample_trade():
    return {
        "e": "aggTrade", "E": 1700000000123, "s": "BTCUSDT", "a": 123,
        "p": "50000", "q": "0.02", "f": 10, "l": 11,
        "T": 1700000000100, "m": False,
    }


def test_aggregate_trade_normalization_and_taker_side():
    buy = normalize_aggregate_trade(sample_trade(), "SPOT")
    assert buy is not None
    assert buy["aggressor_side"] == "BUY"
    assert buy["notional"] == 1000
    payload = sample_trade()
    payload["m"] = True
    sell = normalize_aggregate_trade(payload, "USD_M")
    assert sell is not None
    assert sell["aggressor_side"] == "SELL"
    assert normalize_aggregate_trade({"e": "depthUpdate"}, "SPOT") is None


def test_aggregate_trade_store_is_idempotent_and_filters(tmp_path):
    store = AggregateTradeStore(str(tmp_path / "trades.sqlite3"))
    row = normalize_aggregate_trade(sample_trade(), "SPOT")
    assert row is not None
    store.insert(row)
    store.insert(row)
    assert store.count() == 1
    result = store.recent("SPOT", "BTCUSDT", 10, 1_700_000_000_000, 1_700_000_001_000)
    assert len(result) == 1
    assert result[0]["buyer_is_maker"] is False
    assert store.recent("USD_M", "BTCUSDT") == []


def test_aggregate_trade_store_rejects_lease_with_sqlite_storage(tmp_path):
    import pytest

    store = AggregateTradeStore(str(tmp_path / "trades.sqlite3"))
    row = normalize_aggregate_trade(sample_trade(), "SPOT")
    assert row is not None
    with pytest.raises(ValueError, match="PostgreSQL"):
        store.insert(row, lease=object())


def test_aggregate_trade_stream_urls():
    assert "wss://stream.binance.com:9443/ws/btcusdt@aggTrade" == aggregate_trade_stream_url("SPOT", "BTCUSDT")
    assert "wss://fstream.binance.com/market/ws/btcusdt@aggTrade" == aggregate_trade_stream_url("USD_M", "BTCUSDT")
    assert "wss://dstream.binance.com/ws/btcusd_perp@aggTrade" == aggregate_trade_stream_url("COIN_M", "BTCUSD_PERP")


def test_aggregate_trade_normalization_rejects_invalid_database_values():
    invalid_cases = [
        ("SPOT", {"a": -1}),
        ("SPOT", {"E": -1}),
        ("SPOT", {"T": -1}),
        ("UNKNOWN", {}),
        ("SPOT", {"p": "nan"}),
        ("SPOT", {"q": "inf"}),
        ("SPOT", {"p": "1e308", "q": "1e308"}),
        ("SPOT", {"a": True}),
        ("SPOT", {"E": False}),
    ]
    for market, changes in invalid_cases:
        payload = sample_trade()
        payload.update(changes)
        assert normalize_aggregate_trade(payload, market) is None


def test_aggregate_trade_normalization_trims_symbol_and_rejects_empty_symbol():
    payload = sample_trade()
    payload["s"] = "  btcusdt  "
    normalized = normalize_aggregate_trade(payload, "spot")
    assert normalized is not None
    assert normalized["symbol"] == "BTCUSDT"

    payload["s"] = "   "
    assert normalize_aggregate_trade(payload, "SPOT") is None


def test_aggregate_trade_collector_validates_lease_ttl(tmp_path):
    import pytest
    from app.services.aggregate_trade_stream import AggregateTradeCollector

    with pytest.raises(ValueError, match="ttl_seconds"):
        AggregateTradeCollector(
            AggregateTradeStore(str(tmp_path / "trades.sqlite3")),
            lease_database_url="postgresql://example/db",
            lease_ttl_seconds=2,
        )


def test_aggregate_trade_collector_acquires_stable_lease_and_releases_on_stop(monkeypatch, tmp_path):
    import asyncio
    from types import SimpleNamespace
    from app.services import aggregate_trade_stream as module
    from app.services.aggregate_trade_stream import AggregateTradeCollector

    managers = []

    class FakeLeaseManager:
        def __init__(self, database_url, lease_name, ttl_seconds):
            self.lease_name = lease_name
            self.ttl_seconds = ttl_seconds
            self.released = []
            managers.append(self)
            captured.update(database_url=database_url, lease_name=lease_name, ttl_seconds=ttl_seconds)

        def acquire(self):
            return SimpleNamespace(fencing_token=17)

        def renew(self, lease):
            return lease

        def release(self, lease):
            self.released.append(lease)
            return True

    captured = {}
    monkeypatch.setattr(module, "PostgresCollectorLease", FakeLeaseManager)
    collector = AggregateTradeCollector(
        AggregateTradeStore(str(tmp_path / "trades.sqlite3")),
        jobs_json='[{"market":"USD_M","symbol":"BTCUSDT"}]',
        lease_database_url="postgresql://example/db",
        lease_ttl_seconds=45,
    )
    started = asyncio.Event()

    async def fake_stream(_market, _symbol, _state, _holder, _lost):
        started.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(collector, "_run_stream", fake_stream)

    async def scenario():
        collector.start()
        await asyncio.wait_for(started.wait(), timeout=2)
        state = collector.status()["jobs"][0]
        assert state["lease_state"] == "ACTIVE"
        assert state["lease_name"] == "aggregate-trade:USD_M:BTCUSDT"
        assert state["fencing_token"] == 17
        await collector.stop()

    asyncio.run(scenario())
    assert captured == {
        "database_url": "postgresql://example/db",
        "lease_name": "aggregate-trade:USD_M:BTCUSDT",
        "ttl_seconds": 45,
    }
    assert len(collector.tasks) == 0
    assert len(managers) == 2  # constructor validation plus the per-job runtime manager
    runtime_manager = next(
        manager for manager in managers
        if manager.lease_name == "aggregate-trade:USD_M:BTCUSDT"
    )
    assert len(runtime_manager.released) == 1


def test_aggregate_trade_collector_waits_when_another_owner_holds_lease(monkeypatch, tmp_path):
    import asyncio
    from app.services import aggregate_trade_stream as module
    from app.services.aggregate_trade_stream import AggregateTradeCollector

    class FakeLeaseManager:
        lease_name = "aggregate-trade:SPOT:BTCUSDT"
        ttl_seconds = 30

        def __init__(self, *_args, **_kwargs):
            pass

        def acquire(self):
            return None

    monkeypatch.setattr(module, "PostgresCollectorLease", FakeLeaseManager)
    collector = AggregateTradeCollector(
        AggregateTradeStore(str(tmp_path / "trades.sqlite3")),
        jobs_json='[{"market":"SPOT","symbol":"BTCUSDT"}]',
        lease_database_url="postgresql://example/db",
    )

    async def scenario():
        collector.start()
        for _ in range(100):
            if collector.status()["jobs"] and collector.status()["jobs"][0]["lease_state"] == "HELD_BY_OTHER":
                break
            await asyncio.sleep(0.01)
        assert collector.status()["jobs"][0]["lease_state"] == "HELD_BY_OTHER"
        assert collector.status()["jobs"][0]["connected"] is False
        await collector.stop()

    asyncio.run(scenario())


def test_aggregate_trade_fenced_write_loss_is_terminal(monkeypatch, tmp_path):
    import asyncio
    from types import SimpleNamespace
    import pytest
    from app.services.collector_lease import CollectorLeaseLostError
    from app.services.aggregate_trade_stream import AggregateTradeCollector

    class FailingStore:
        def insert(self, _row, lease=None):
            raise CollectorLeaseLostError("stale owner")

        def count(self):
            return 0

    collector = AggregateTradeCollector(FailingStore())
    state = {"lease_state": "ACTIVE", "last_error": None}
    lost = asyncio.Event()
    holder = {"lease": SimpleNamespace(fencing_token=4)}
    row = normalize_aggregate_trade(sample_trade(), "SPOT")

    async def scenario():
        with pytest.raises(CollectorLeaseLostError):
            await collector._persist_trade(row, holder, lost, state)

    asyncio.run(scenario())
    assert lost.is_set()
    assert state["lease_state"] == "LOST"
    assert state["last_error"] == "CollectorLeaseLostError"


def test_aggregate_trade_collector_stops_when_lease_renewal_is_lost(monkeypatch, tmp_path):
    import asyncio
    from types import SimpleNamespace
    from app.services import aggregate_trade_stream as module
    from app.services.aggregate_trade_stream import AggregateTradeCollector

    managers = []

    class FakeLeaseManager:
        lease_name = "aggregate-trade:SPOT:BTCUSDT"
        ttl_seconds = 5

        def __init__(self, *_args, **_kwargs):
            self.released = []
            managers.append(self)

        def acquire(self):
            return SimpleNamespace(fencing_token=8)

        def renew(self, _lease):
            return None

        def release(self, lease):
            self.released.append(lease)
            return True

    monkeypatch.setattr(module, "PostgresCollectorLease", FakeLeaseManager)
    collector = AggregateTradeCollector(
        AggregateTradeStore(str(tmp_path / "trades.sqlite3")),
        jobs_json='[{"market":"SPOT","symbol":"BTCUSDT"}]',
        lease_database_url="postgresql://example/db",
        lease_ttl_seconds=5,
    )
    stream_started = asyncio.Event()

    async def fake_stream(_market, _symbol, _state, _holder, _lost):
        stream_started.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(collector, "_run_stream", fake_stream)

    async def scenario():
        collector.start()
        await asyncio.wait_for(stream_started.wait(), timeout=2)
        for _ in range(200):
            state = collector.status()["jobs"][0]
            if state["lease_state"] == "LOST":
                break
            await asyncio.sleep(0.01)
        assert collector.status()["jobs"][0]["lease_state"] == "LOST"
        await collector.stop()

    asyncio.run(scenario())
    assert len(managers) == 2  # constructor validation plus the per-job runtime manager
    runtime_manager = next(
        manager for manager in managers
        if manager.lease_name == "aggregate-trade:SPOT:BTCUSDT"
    )
    assert runtime_manager.released == []
