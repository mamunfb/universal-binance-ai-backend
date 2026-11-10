import json

import pytest

from app.services.advanced_derivatives_analysis import (
    AdvancedDerivativesAnalysis, DerivativesSignalStore,
)
from app.services.funding_rates import FundingRateStore
from app.services.historical_klines import HistoricalKlineStore
from app.services.liquidation_collector import LiquidationStore
from app.services.open_interest import OpenInterestStore


def build_engine(tmp_path):
    funding = FundingRateStore(str(tmp_path / "funding.sqlite3"))
    oi = OpenInterestStore(str(tmp_path / "oi.sqlite3"))
    klines = HistoricalKlineStore(str(tmp_path / "klines.sqlite3"))
    liquidations = LiquidationStore(str(tmp_path / "liquidations.sqlite3"))
    signals = DerivativesSignalStore(str(tmp_path / "signals.sqlite3"))
    return AdvancedDerivativesAnalysis(funding, oi, klines, liquidations, signals), (
        funding, oi, klines, liquidations, signals
    )


def seed_series(stores):
    funding, oi, klines, liquidations, _signals = stores
    start = 1700000000000
    oi_values = [100, 101, 102, 103, 104, 105, 125]
    oi.save("USD_M", "BTCUSDT", "1h", [
        {"symbol": "BTCUSDT", "timestamp": start + i * 3600000,
         "sumOpenInterest": str(value), "sumOpenInterestValue": str(value * 50000)}
        for i, value in enumerate(oi_values)
    ])
    funding.save("USD_M", "BTCUSDT", [
        {"symbol": "BTCUSDT", "fundingTime": start + 6 * 3600000,
         "fundingRate": "0.002", "markPrice": "52000"}
    ])
    klines.save_klines("USD_M", "BTCUSDT", "1h", [
        [start + i * 3600000, str(50000 + i * 100), str(50100 + i * 100),
         str(49900 + i * 100), str(50050 + i * 100), "10",
         start + (i + 1) * 3600000 - 1, "500000", 100, "5", "250000"]
        for i in range(7)
    ])
    liquidations.insert({
        "event_time_ms": start + 6 * 3600000,
        "trade_time_ms": start + 6 * 3600000,
        "symbol": "BTCUSDT", "pair_symbol": None, "market_type": None,
        "side": "SELL", "order_type": "LIMIT", "status": "FILLED",
        "average_price": 52000.0, "original_quantity": 1.0,
        "last_filled_quantity": 1.0, "cumulative_filled_quantity": 1.0,
        "approx_cumulative_notional": 52000.0,
        "raw_json": json.dumps({"e": "forceOrder"}),
    })


def test_advanced_analysis_detects_oi_spike_divergence_and_funding_extreme(tmp_path):
    engine, stores = build_engine(tmp_path)
    seed_series(stores)
    result = engine.analyze("btcusdt", "1h", "1h", 48)
    assert result["status"] == "COMPLETED"
    assert result["trend"]["direction"] == "OI_RISING"
    assert result["trend"]["acceleration_state"] == "ACCELERATING_UP"
    assert result["oi_spike"]["status"] == "SPIKE_CANDIDATE"
    assert result["price_oi_divergence"]["classification"] == "NO_DIVERGENCE_DETECTED"
    assert result["funding_extreme"]["is_extreme_by_configured_threshold"] is True
    assert result["liquidation_context"]["stored_events_in_window"] == 1
    assert result["liquidation_context"]["by_force_order_side"]["SELL"]["count"] == 1
    assert result["signal_storage"]["status"] == "STORED"


def test_signal_history_is_idempotent_and_ordered(tmp_path):
    engine, stores = build_engine(tmp_path)
    seed_series(stores)
    engine.analyze("BTCUSDT", "1h", "1h", 48)
    engine.analyze("BTCUSDT", "1h", "1h", 48)
    history = stores[-1].history("BTCUSDT", "1h")
    assert history["returned_count"] == 1
    assert history["snapshots"][0]["analysis"]["status"] == "COMPLETED"


def test_advanced_analysis_requires_six_oi_records(tmp_path):
    engine, stores = build_engine(tmp_path)
    stores[1].save("USD_M", "BTCUSDT", "1h", [
        {"symbol": "BTCUSDT", "timestamp": 1700000000000 + i * 3600000,
         "sumOpenInterest": "100", "sumOpenInterestValue": "100000"}
        for i in range(5)
    ])
    result = engine.analyze("BTCUSDT")
    assert result["status"] == "INSUFFICIENT_DATA"
    assert result["analysis"] is None


@pytest.mark.parametrize("kwargs", [
    {"funding_abs_threshold": -1},
    {"spike_mad_multiplier": 0},
    {"limit": 5},
])
def test_advanced_analysis_rejects_invalid_parameters(tmp_path, kwargs):
    engine, _stores = build_engine(tmp_path)
    with pytest.raises(ValueError):
        engine.analyze("BTCUSDT", **kwargs)
