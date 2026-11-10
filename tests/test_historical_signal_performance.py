import pytest

from app.services.advanced_derivatives_analysis import DerivativesSignalStore
from app.services.historical_klines import HistoricalKlineStore
from app.services.historical_signal_performance import HistoricalSignalPerformance


def _candle(ts, close):
    return [ts, "100", str(max(100, close) + 2), "98", str(close),
            "10", ts + 3_599_999, "1000", 20, "4", "400", "0"]


def _engine(tmp_path):
    signals = DerivativesSignalStore(str(tmp_path / "signals.sqlite3"))
    klines = HistoricalKlineStore(str(tmp_path / "klines.sqlite3"))
    return HistoricalSignalPerformance(signals, klines), signals, klines


def test_forward_outcomes_use_only_future_completed_candles(tmp_path):
    engine, signals, klines = _engine(tmp_path)
    hour = 3_600_000
    klines.save_klines("USD_M", "BTCUSDT", "1h", [
        _candle(i * hour, 100 + i) for i in range(26)
    ])
    signals.save({
        "status": "COMPLETED", "symbol": "BTCUSDT", "period": "1h",
        "window": {"end_time_ms": hour},
        "positioning_context": {"classification": "PRICE_UP_OI_UP_BUILDUP_CANDIDATE"},
    })

    result = engine.evaluate("BTCUSDT", "1h", "1h", 100, 10)
    assert result["status"] == "COMPLETED"
    assert result["evaluated_signal_count"] == 1
    assert result["horizons"]["1"]["sample_size"] == 1
    outcome = result["horizons"]["1"]["outcomes"][0]
    assert outcome["baseline_close"] == 100
    assert outcome["outcome_close"] == 101
    assert outcome["gross_return_percent"] == pytest.approx(1.0)
    assert outcome["net_hypothetical_return_percent"] == pytest.approx(0.9)
    assert outcome["actual_elapsed_hours"] == pytest.approx(1.0)
    assert result["horizons"]["4"]["sample_size"] == 1
    assert result["horizons"]["24"]["sample_size"] == 1
    assert "only when a snapshot contains an explicit" in result["method"]["directional_accuracy"]


def test_outcomes_remain_pending_until_future_candles_exist(tmp_path):
    engine, signals, klines = _engine(tmp_path)
    hour = 3_600_000
    klines.save_klines("USD_M", "BTCUSDT", "1h", [
        _candle(0, 100),
    ])
    signals.save({
        "status": "COMPLETED", "symbol": "BTCUSDT", "period": "1h",
        "window": {"end_time_ms": hour},
    })
    result = engine.evaluate("BTCUSDT")
    assert result["status"] == "INSUFFICIENT_FUTURE_DATA"
    assert result["horizons"]["1"]["sample_size"] == 0
    assert result["horizons"]["1"]["pending_or_not_yet_matured"] == 1


def test_performance_evaluator_validates_cost_and_limit(tmp_path):
    engine, _signals, _klines = _engine(tmp_path)
    with pytest.raises(ValueError):
        engine.evaluate("BTCUSDT", round_trip_cost_bps=-1)
    with pytest.raises(ValueError):
        engine.evaluate("BTCUSDT", limit=0)


def test_directional_signal_validation_requires_explicit_hypothesis_and_reports_wilson_interval():
    from app.services.historical_signal_performance import (
        _explicit_signal_direction, _signal_quality,
    )

    assert _explicit_signal_direction({
        "positioning_context": {"classification": "PRICE_UP_OI_UP_BUILDUP_CANDIDATE"},
    }) is None
    assert _explicit_signal_direction({"signal_direction": "BUY"}) == "BULLISH"
    assert _explicit_signal_direction({
        "directional_signal": {"direction": "SHORT"},
    }) == "BEARISH"
    assert _explicit_signal_direction({"confluence": {"bias": "BULLISH"}}) == "BULLISH"

    rows = [
        {"signal_direction": "BULLISH", "gross_return_percent": 2.0},
        {"signal_direction": "BULLISH", "gross_return_percent": -1.0},
        {"signal_direction": "BEARISH", "gross_return_percent": -3.0},
        {"signal_direction": "BEARISH", "gross_return_percent": 0.0},
        {"signal_direction": None, "gross_return_percent": 5.0},
    ]
    result = _signal_quality(rows)
    assert result["status"] == "DIRECTIONAL_HYPOTHESIS_AVAILABLE"
    assert result["prediction_count"] == 4
    assert result["scored_non_flat_count"] == 3
    assert result["directional_hit_count"] == 2
    assert result["directional_miss_count"] == 1
    assert result["flat_outcome_count"] == 1
    assert result["directional_hit_rate"] == pytest.approx(2 / 3)
    assert result["directional_hit_rate_ci_95_wilson"]["lower"] < 2 / 3
    assert result["directional_hit_rate_ci_95_wilson"]["upper"] > 2 / 3
    assert result["false_positive_count"] is None
    assert result["false_negative_count"] is None


def test_directional_signal_validation_withholds_accuracy_without_explicit_signal():
    from app.services.historical_signal_performance import _signal_quality

    result = _signal_quality([
        {"signal_direction": None, "gross_return_percent": 1.0},
        {"signal_direction": None, "gross_return_percent": -1.0},
    ])
    assert result["status"] == "NO_EXPLICIT_DIRECTIONAL_HYPOTHESIS"
    assert result["prediction_count"] == 0
    assert result["directional_hit_rate"] is None
    assert result["directional_hit_rate_ci_95_wilson"] is None
