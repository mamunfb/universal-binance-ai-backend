from types import SimpleNamespace

import pytest

from app.services.aggregate_trade_stream import AggregateTradeCollector
from app.services.derivatives_collector import DerivativesHistoryCollector
from app.services.historical_collector import HistoricalKlineCollector
from app.services.liquidation_collector import LiquidationCollector
from app.services.order_book_stream import OrderBookStreamCollector


POSTGRES_URL = "postgresql://example/test"


def test_aggregate_trade_collector_rejects_postgres_store_without_lease_url():
    with pytest.raises(ValueError, match="requires lease_database_url"):
        AggregateTradeCollector(SimpleNamespace(database_url=POSTGRES_URL))


def test_order_book_collector_rejects_postgres_store_without_lease_url():
    with pytest.raises(ValueError, match="requires lease_database_url"):
        OrderBookStreamCollector(
            SimpleNamespace(database_url=POSTGRES_URL),
            lambda: None,
            lambda _market: None,
        )


def test_liquidation_collector_rejects_postgres_store_without_lease_url():
    with pytest.raises(ValueError, match="requires lease_database_url"):
        LiquidationCollector(SimpleNamespace(database_url=POSTGRES_URL))


def test_derivatives_collector_rejects_postgres_stores_without_lease_url():
    with pytest.raises(ValueError, match="requires lease_database_url"):
        DerivativesHistoryCollector(
            SimpleNamespace(database_url=POSTGRES_URL),
            SimpleNamespace(database_url=POSTGRES_URL),
            lambda _market: None,
            "[]",
        )


def test_historical_collector_rejects_postgres_store_without_lease_url():
    with pytest.raises(ValueError, match="requires lease_database_url"):
        HistoricalKlineCollector(
            SimpleNamespace(database_url=POSTGRES_URL),
            lambda: None,
            lambda _market: None,
        )
