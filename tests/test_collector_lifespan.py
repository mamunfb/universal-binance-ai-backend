from types import SimpleNamespace

import pytest

from app import main


def _disable_all_collectors(monkeypatch):
    for name in (
        "liquidation_collector_enabled",
        "order_book_collector_enabled",
        "aggregate_trade_collector_enabled",
        "derivatives_collector_enabled",
        "historical_collector_enabled",
    ):
        monkeypatch.setattr(main.settings, name, False)
    monkeypatch.setattr(main.settings, "require_database_url", False)
    monkeypatch.setattr(main.settings, "database_url", "")
    main.order_book_collector = None
    main.aggregate_trade_collector = None
    main.derivatives_collector = None
    main.historical_collector = None


@pytest.mark.asyncio
async def test_lifespan_cleans_up_collector_when_later_startup_fails(monkeypatch):
    _disable_all_collectors(monkeypatch)
    monkeypatch.setattr(main.settings, "order_book_collector_enabled", True)
    monkeypatch.setattr(main, "OrderBookStreamCollector", lambda **_kwargs: SimpleNamespace())
    stopped = []

    def fail_start(_name, _collector):
        raise RuntimeError("simulated startup failure")

    async def stop_collector(name, _collector):
        stopped.append(name)

    monkeypatch.setattr(main, "_start_collector_with_lease", fail_start)
    monkeypatch.setattr(main, "_stop_collector_with_lease", stop_collector)

    with pytest.raises(RuntimeError, match="simulated startup failure"):
        async with main.lifespan(main.app):
            pass

    assert stopped == ["order-book:all"]
    assert main.order_book_collector is None


@pytest.mark.asyncio
async def test_lifespan_attempts_remaining_shutdown_after_one_stop_fails(monkeypatch):
    _disable_all_collectors(monkeypatch)
    monkeypatch.setattr(main.settings, "order_book_collector_enabled", True)
    monkeypatch.setattr(main.settings, "aggregate_trade_collector_enabled", True)
    monkeypatch.setattr(main, "OrderBookStreamCollector", lambda **_kwargs: SimpleNamespace())
    monkeypatch.setattr(
        main, "AggregateTradeCollector",
        lambda **_kwargs: SimpleNamespace(),
    )
    monkeypatch.setattr(main, "_start_collector_with_lease", lambda *_args: None)
    stopped = []

    async def stop_collector(name, _collector):
        stopped.append(name)
        if name == "order-book:all":
            raise RuntimeError("simulated stop failure")

    monkeypatch.setattr(main, "_stop_collector_with_lease", stop_collector)

    with pytest.raises(RuntimeError, match=r"collector\(s\) failed to stop cleanly"):
        async with main.lifespan(main.app):
            pass

    assert stopped == ["order-book:all", "aggregate-trades:all"]
    assert main.order_book_collector is None
    assert main.aggregate_trade_collector is None
