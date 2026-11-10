from app.services.market_confluence_performance import MarketConfluencePerformance


class SnapshotStore:
    def __init__(self, snapshots):
        self.snapshots = snapshots

    def history(self, market, symbol, interval, limit):
        return {"returned_count": len(self.snapshots), "snapshots": self.snapshots}


class KlineStore:
    def history(self, market, symbol, interval, start_time_ms, end_time_ms, limit):
        target = end_time_ms - 3_600_000
        if self.empty:
            return {"candles": []}
        return {"candles": [{
            "open_time_ms": start_time_ms,
            "close_time_ms": target,
            "high": 110.0,
            "low": 90.0,
            "close": 105.0,
        }]}

    empty = False


def snapshot(bias):
    return {
        "snapshot_id": bias,
        "analyzed_at_ms": 1_000_000,
        "bias": bias,
        "alignment": "TEST",
        "reference_price": 100.0,
    }


def test_directional_outcomes_and_mixed_exclusion():
    evaluator = MarketConfluencePerformance(
        SnapshotStore([snapshot("BULLISH"), snapshot("BEARISH"), snapshot("MIXED")]),
        KlineStore(),
    )
    result = evaluator.evaluate("USD_M", "BTCUSDT", "1h", "1h", 10)
    one_hour = result["horizons"]["1"]
    assert one_hour["sample_size"] == 3
    assert one_hour["directional_sample_size"] == 2
    assert one_hour["directional_positive_fraction"] == 0.5
    assert one_hour["outcomes"][0]["directional_return_percent"] == 5.0
    assert one_hour["outcomes"][1]["directional_return_percent"] == -5.0
    assert one_hour["outcomes"][2]["directional_return_percent"] is None


def test_missing_future_candles_remain_pending():
    klines = KlineStore()
    klines.empty = True
    evaluator = MarketConfluencePerformance(SnapshotStore([snapshot("BULLISH")]), klines)
    result = evaluator.evaluate("USD_M", "BTCUSDT", "1h", "1h", 10)
    assert result["horizons"]["1"]["status"] == "INSUFFICIENT_FUTURE_DATA"
    assert result["horizons"]["1"]["pending_or_not_matured"] == 1
    assert result["horizons"]["1"]["directional_positive_fraction"] is None



def test_all_seven_horizons_are_reported_and_one_month_is_30_days():
    evaluator = MarketConfluencePerformance(SnapshotStore([]), KlineStore())
    result = evaluator.evaluate("USD_M", "BTCUSDT", "1h", "1h", 10)
    assert set(result["horizons"]) == {"1", "4", "24", "48", "72", "360", "720"}
    assert result["horizons"]["360"]["horizon_days"] == 15
    assert result["horizons"]["720"]["horizon_days"] == 30
    assert result["method"]["one_month"].startswith("30 fixed days")


def test_hourly_candles_are_the_default_resolution():
    evaluator = MarketConfluencePerformance(SnapshotStore([]), KlineStore())
    result = evaluator.evaluate("USD_M", "BTCUSDT")
    assert result["price_interval"] == "1h"


def test_one_minute_interval_rejected_for_long_horizon_query():
    evaluator = MarketConfluencePerformance(SnapshotStore([]), KlineStore())
    try:
        evaluator.evaluate("USD_M", "BTCUSDT", price_interval="1m")
    except ValueError as exc:
        assert "price_interval" in str(exc)
    else:
        raise AssertionError("1m interval must be rejected to avoid truncating the 30-day candle window")


class PricePathSnapshotStore(SnapshotStore):
    def get_snapshot(self, market, symbol, snapshot_id):
        return {
            "snapshot_id": snapshot_id, "analyzed_at_ms": 3_600_000,
            "bias": "BULLISH", "alignment": "ALIGNED",
            "reference_price": 100.0, "reference_close_time_ms": 3_599_999,
        }


class PricePathKlineStore:
    def history(self, market, symbol, interval, start_time_ms, end_time_ms, limit):
        return {"candles": [
            {"open_time_ms": 7_200_000, "close_time_ms": 10_799_999,
             "open": 100.0, "high": 104.0, "low": 99.0, "close": 103.0},
            {"open_time_ms": 10_800_000, "close_time_ms": 14_399_999,
             "open": 103.0, "high": 105.0, "low": 102.0, "close": 104.0},
        ]}


def test_snapshot_price_path_returns_hourly_candles_and_reference_change():
    engine = MarketConfluencePerformance(PricePathSnapshotStore([]), PricePathKlineStore())
    result = engine.price_path("USD_M", "BTCUSDT", "snapshot-1", "1h", 2)
    assert result["status"] == "COMPLETED"
    assert len(result["candles"]) == 2
    assert result["candles"][0]["change_from_reference_percent"] == 3.0
    assert result["coverage"]["complete"] is True


def test_snapshot_price_path_rejects_more_than_30_days():
    engine = MarketConfluencePerformance(PricePathSnapshotStore([]), PricePathKlineStore())
    try:
        engine.price_path("USD_M", "BTCUSDT", "snapshot-1", "1h", 721)
    except ValueError as exc:
        assert "hours" in str(exc)
    else:
        raise AssertionError("Price path must be capped at 720 hours")


def test_snapshot_price_path_marks_horizon_pending_until_target_candle_closes():
    class EarlyKlines:
        def history(self, market, symbol, interval, start_time_ms, end_time_ms, limit):
            return {"candles": [
                {"open_time_ms": 7_200_000, "close_time_ms": 10_799_999,
                 "open": 100.0, "high": 104.0, "low": 99.0, "close": 103.0},
            ]}
    engine = MarketConfluencePerformance(PricePathSnapshotStore([]), EarlyKlines())
    result = engine.price_path("USD_M", "BTCUSDT", "snapshot-1", "1h", 2)
    assert result["status"] == "PENDING_HORIZON_NOT_MATURED"
    assert result["target_reached"] is False
    assert len(result["candles"]) == 1


def test_evaluate_returns_summary_and_bias_specific_accuracy_breakdown():
    evaluator = MarketConfluencePerformance(
        SnapshotStore([snapshot("BULLISH"), snapshot("BEARISH"), snapshot("MIXED")]),
        KlineStore(),
    )
    result = evaluator.evaluate("USD_M", "BTCUSDT", "1h", "1h", 10)
    assert result["status"] == "COMPLETED"
    breakdown = result["horizons"]["1"]["bias_breakdown"]
    assert breakdown["BULLISH"]["sample_size"] == 1
    assert breakdown["BULLISH"]["positive_fraction"] == 1.0
    assert breakdown["BEARISH"]["sample_size"] == 1
    assert breakdown["BEARISH"]["positive_fraction"] == 0.0
    assert breakdown["MIXED"]["sample_size"] == 1
    assert breakdown["MIXED"]["positive_fraction"] is None
