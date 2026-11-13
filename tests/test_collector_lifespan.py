import asyncio

import pytest

from app import main


class _StartedCollector:
    def __init__(self):
        self.started = False
        self.stopped = False

    def start(self):
        self.started = True

    async def stop(self):
        self.stopped = True


def test_lifespan_cleans_up_started_collectors_when_later_startup_fails(monkeypatch):
    async def scenario():
        liquidation = _StartedCollector()
        monkeypatch.setattr(main, "liquidation_collector", liquidation)
        monkeypatch.setattr(main.settings, "require_database_url", False)
        monkeypatch.setattr(main.settings, "liquidation_collector_enabled", True)
        monkeypatch.setattr(main.settings, "order_book_collector_enabled", True)
        monkeypatch.setattr(main.settings, "order_book_collector_jobs", "not-json")
        monkeypatch.setattr(main.settings, "aggregate_trade_collector_enabled", False)
        monkeypatch.setattr(main.settings, "derivatives_collector_enabled", False)
        monkeypatch.setattr(main.settings, "historical_collector_enabled", False)
        monkeypatch.setattr(main, "order_book_collector", None)
        monkeypatch.setattr(main, "aggregate_trade_collector", None)
        monkeypatch.setattr(main, "derivatives_collector", None)
        monkeypatch.setattr(main, "historical_collector", None)

        lifespan_context = main.lifespan(main.app)
        with pytest.raises(ValueError, match="ORDER_BOOK_COLLECTOR_JOBS"):
            await lifespan_context.__aenter__()

        assert liquidation.started is True
        assert liquidation.stopped is True
        assert main.order_book_collector is None

    asyncio.run(scenario())


class _FailingStopCollector(_StartedCollector):
    async def stop(self):
        self.stopped = True
        raise RuntimeError("simulated shutdown failure")


def test_lifespan_attempts_remaining_shutdowns_after_one_collector_fails(monkeypatch):
    async def scenario():
        order_book = _FailingStopCollector()
        aggregate = _StartedCollector()

        class _OrderBookFactory:
            def __new__(cls, **kwargs):
                return order_book

        class _AggregateFactory:
            def __new__(cls, **kwargs):
                return aggregate

        monkeypatch.setattr(main.settings, "require_database_url", False)
        monkeypatch.setattr(main.settings, "liquidation_collector_enabled", False)
        monkeypatch.setattr(main.settings, "order_book_collector_enabled", True)
        monkeypatch.setattr(main.settings, "aggregate_trade_collector_enabled", True)
        monkeypatch.setattr(main.settings, "derivatives_collector_enabled", False)
        monkeypatch.setattr(main.settings, "historical_collector_enabled", False)
        monkeypatch.setattr(main, "OrderBookStreamCollector", _OrderBookFactory)
        monkeypatch.setattr(main, "AggregateTradeCollector", _AggregateFactory)
        monkeypatch.setattr(main, "order_book_collector", None)
        monkeypatch.setattr(main, "aggregate_trade_collector", None)
        monkeypatch.setattr(main, "derivatives_collector", None)
        monkeypatch.setattr(main, "historical_collector", None)

        async with main.lifespan(main.app):
            assert order_book.started is True
            assert aggregate.started is True

        assert order_book.stopped is True
        assert aggregate.stopped is True

    asyncio.run(scenario())


def test_lifespan_does_not_construct_collectors_when_all_flags_disabled(monkeypatch):
    async def scenario():
        def unexpected_factory(**kwargs):
            raise AssertionError("disabled collector factory must not be called")

        monkeypatch.setattr(main.settings, "require_database_url", False)
        for flag in (
            "liquidation_collector_enabled",
            "order_book_collector_enabled",
            "aggregate_trade_collector_enabled",
            "derivatives_collector_enabled",
            "historical_collector_enabled",
        ):
            monkeypatch.setattr(main.settings, flag, False)

        for name in (
            "OrderBookStreamCollector",
            "AggregateTradeCollector",
            "DerivativesHistoryCollector",
            "HistoricalKlineCollector",
        ):
            monkeypatch.setattr(main, name, unexpected_factory)

        monkeypatch.setattr(main, "order_book_collector", None)
        monkeypatch.setattr(main, "aggregate_trade_collector", None)
        monkeypatch.setattr(main, "derivatives_collector", None)
        monkeypatch.setattr(main, "historical_collector", None)

        async with main.lifespan(main.app):
            assert main.order_book_collector is None
            assert main.aggregate_trade_collector is None
            assert main.derivatives_collector is None
            assert main.historical_collector is None

    asyncio.run(scenario())


class _HangingStopCollector(_StartedCollector):
    def __init__(self):
        super().__init__()
        self.stop_entered = False
        self.stop_cancelled = False

    async def stop(self):
        self.stop_entered = True
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.stop_cancelled = True
            raise


def test_lifespan_bounds_shutdown_and_continues_other_collectors(monkeypatch):
    async def scenario():
        hanging = _HangingStopCollector()
        aggregate = _StartedCollector()

        class _OrderBookFactory:
            def __new__(cls, **kwargs):
                return hanging

        class _AggregateFactory:
            def __new__(cls, **kwargs):
                return aggregate

        monkeypatch.setattr(main.settings, "require_database_url", False)
        monkeypatch.setattr(main.settings, "collector_shutdown_timeout_seconds", 0.01)
        monkeypatch.setattr(main.settings, "liquidation_collector_enabled", False)
        monkeypatch.setattr(main.settings, "order_book_collector_enabled", True)
        monkeypatch.setattr(main.settings, "aggregate_trade_collector_enabled", True)
        monkeypatch.setattr(main.settings, "derivatives_collector_enabled", False)
        monkeypatch.setattr(main.settings, "historical_collector_enabled", False)
        monkeypatch.setattr(main, "OrderBookStreamCollector", _OrderBookFactory)
        monkeypatch.setattr(main, "AggregateTradeCollector", _AggregateFactory)
        monkeypatch.setattr(main, "order_book_collector", None)
        monkeypatch.setattr(main, "aggregate_trade_collector", None)
        monkeypatch.setattr(main, "derivatives_collector", None)
        monkeypatch.setattr(main, "historical_collector", None)

        async with main.lifespan(main.app):
            assert hanging.started is True
            assert aggregate.started is True

        assert hanging.stop_entered is True
        assert hanging.stop_cancelled is True
        assert aggregate.stopped is True

    asyncio.run(scenario())
