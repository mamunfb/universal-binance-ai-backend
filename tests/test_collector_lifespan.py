import pytest

from app import main


@pytest.mark.anyio
async def test_lifespan_stops_started_collectors_when_later_startup_fails(monkeypatch):
    events = []

    class FakeLiquidationCollector:
        def start(self):
            events.append("liquidation-start")

        async def stop(self):
            events.append("liquidation-stop")

    class FailingOrderBookCollector:
        def __init__(self, **kwargs):
            pass

        def start(self):
            events.append("order-book-start")
            raise RuntimeError("simulated collector startup failure")

        async def stop(self):
            events.append("order-book-stop")
            raise RuntimeError("simulated collector shutdown failure")

    monkeypatch.setattr(main.settings, "require_database_url", False)
    monkeypatch.setattr(main.settings, "liquidation_collector_enabled", True)
    monkeypatch.setattr(main.settings, "order_book_collector_enabled", True)
    monkeypatch.setattr(main.settings, "aggregate_trade_collector_enabled", False)
    monkeypatch.setattr(main.settings, "derivatives_collector_enabled", False)
    monkeypatch.setattr(main.settings, "historical_collector_enabled", False)
    monkeypatch.setattr(main, "liquidation_collector", FakeLiquidationCollector())
    monkeypatch.setattr(main, "OrderBookStreamCollector", FailingOrderBookCollector)
    monkeypatch.setattr(main, "order_book_collector", None)
    monkeypatch.setattr(main, "aggregate_trade_collector", None)
    monkeypatch.setattr(main, "derivatives_collector", None)
    monkeypatch.setattr(main, "historical_collector", None)

    with pytest.raises(RuntimeError, match="simulated collector startup failure"):
        async with main.lifespan(main.app):
            pytest.fail("lifespan should not yield after collector startup fails")

    assert events == [
        "liquidation-start",
        "order-book-start",
        "order-book-stop",
        "liquidation-stop",
    ]
    assert main.order_book_collector is None


@pytest.mark.anyio
async def test_lifespan_rejects_enabled_aggregate_trade_collector_without_jobs(monkeypatch):
    monkeypatch.setattr(main.settings, "require_database_url", False)
    monkeypatch.setattr(main.settings, "liquidation_collector_enabled", False)
    monkeypatch.setattr(main.settings, "order_book_collector_enabled", False)
    monkeypatch.setattr(main.settings, "aggregate_trade_collector_enabled", True)
    monkeypatch.setattr(main.settings, "aggregate_trade_collector_jobs", "[]")
    monkeypatch.setattr(main.settings, "derivatives_collector_enabled", False)
    monkeypatch.setattr(main.settings, "historical_collector_enabled", False)
    monkeypatch.setattr(main, "aggregate_trade_collector", None)

    with pytest.raises(
        ValueError,
        match="AGGREGATE_TRADE_COLLECTOR_JOBS must contain at least one job",
    ):
        async with main.lifespan(main.app):
            pytest.fail("lifespan must reject an enabled collector with no jobs")

    assert main.aggregate_trade_collector is None
