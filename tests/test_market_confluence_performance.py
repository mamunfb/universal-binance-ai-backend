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


def test_regime_breakdown_uses_saved_evidence_and_unclassified_fallback():
    bullish = snapshot("BULLISH")
    bullish["payload"] = {"evidence": [{"source": "MARKET_REGIME", "detail": {
        "regime": "TRENDING", "volatility_regime": "HIGH", "structure_regime": "EXPANSION",
    }}]}
    bearish = snapshot("BEARISH")
    bearish["payload"] = {"evidence": [{"source": "MARKET_REGIME", "detail": {
        "regime": "RANGING", "volatility_regime": "LOW", "structure_regime": "COMPRESSION",
    }}]}
    unknown = snapshot("MIXED")
    unknown["payload"] = {"evidence": []}
    evaluator = MarketConfluencePerformance(SnapshotStore([bullish, bearish, unknown]), KlineStore())
    result = evaluator.evaluate("USD_M", "BTCUSDT", "1h", "1h", 10)
    one_hour = result["horizons"]["1"]
    regimes = one_hour["regime_breakdown"]["market_regime"]
    assert regimes["TRENDING"]["sample_size"] == 1
    assert regimes["TRENDING"]["positive_fraction"] == 1.0
    assert regimes["RANGING"]["positive_fraction"] == 0.0
    assert regimes["UNCLASSIFIED"]["sample_size"] == 1
    assert regimes["UNCLASSIFIED"]["positive_fraction"] is None
    assert one_hour["regime_breakdown"]["volatility_regime"]["HIGH"]["sample_size"] == 1

 

def test_combined_market_regime_and_bias_breakdown_is_separate_per_horizon():
    trending_bull = snapshot("BULLISH")
    trending_bull["payload"] = {"evidence": [{"source": "MARKET_REGIME", "detail": {"regime": "TRENDING"}}]}
    trending_bear = snapshot("BEARISH")
    trending_bear["payload"] = {"evidence": [{"source": "MARKET_REGIME", "detail": {"regime": "TRENDING"}}]}
    ranging_bull = snapshot("BULLISH")
    ranging_bull["payload"] = {"evidence": [{"source": "MARKET_REGIME", "detail": {"regime": "RANGING"}}]}
    evaluator = MarketConfluencePerformance(
        SnapshotStore([trending_bull, trending_bear, ranging_bull]), KlineStore(),
    )
    result = evaluator.evaluate("USD_M", "BTCUSDT", "1h", "1h", 10)
    one_hour = result["horizons"]["1"]
    grouped = one_hour["regime_bias_breakdown"]["market_regime"]
    assert grouped["TRENDING"]["BULLISH"]["sample_size"] == 1
    assert grouped["TRENDING"]["BULLISH"]["positive_fraction"] == 1.0
    assert grouped["TRENDING"]["BEARISH"]["sample_size"] == 1
    assert grouped["TRENDING"]["BEARISH"]["positive_fraction"] == 0.0
    assert grouped["RANGING"]["BULLISH"]["sample_size"] == 1
    assert grouped["RANGING"]["BEARISH"]["sample_size"] == 0


def test_chronological_out_of_sample_holdout_uses_latest_snapshots_only():
    first = snapshot("BULLISH")
    first["snapshot_id"] = "first"
    first["analyzed_at_ms"] = 1_000_000
    second = snapshot("BEARISH")
    second["snapshot_id"] = "second"
    second["analyzed_at_ms"] = 2_000_000
    third = snapshot("BEARISH")
    third["snapshot_id"] = "third"
    third["analyzed_at_ms"] = 3_000_000
    fourth = snapshot("BEARISH")
    fourth["snapshot_id"] = "fourth"
    fourth["analyzed_at_ms"] = 4_000_000
    evaluator = MarketConfluencePerformance(
        SnapshotStore([fourth, second, first, third]), KlineStore(),
    )
    result = evaluator.evaluate("USD_M", "BTCUSDT", "1h", "1h", 10)
    holdout = result["horizons"]["1"]["out_of_sample"]
    assert holdout["status"] == "COMPLETED"
    assert holdout["training_snapshot_count"] == 2
    assert holdout["test_snapshot_count"] == 2
    assert holdout["split_timestamp_ms"] == 2_000_000
    assert [row["snapshot_id"] for row in holdout["test_outcomes"]] == ["third", "fourth"]
    assert holdout["test_directional_sample_size"] == 2
    assert holdout["test_directional_positive_fraction"] == 0.0


def test_out_of_sample_requires_at_least_two_snapshots():
    evaluator = MarketConfluencePerformance(SnapshotStore([snapshot("BULLISH")]), KlineStore())
    result = evaluator.evaluate("USD_M", "BTCUSDT", "1h", "1h", 10)
    holdout = result["horizons"]["1"]["out_of_sample"]
    assert holdout["status"] == "INSUFFICIENT_SNAPSHOTS"
    assert holdout["training_snapshot_count"] == 0
    assert holdout["test_snapshot_count"] == 1
    assert holdout["test_directional_positive_fraction"] is None


def test_walk_forward_uses_expanding_training_windows_and_disjoint_test_blocks():
    rows = []
    for index, bias in enumerate(["BULLISH", "BULLISH", "BEARISH", "BEARISH", "BULLISH", "BEARISH"], start=1):
        item = snapshot(bias)
        item["snapshot_id"] = f"wf-{index}"
        item["analyzed_at_ms"] = index * 1_000_000
        rows.append(item)
    evaluator = MarketConfluencePerformance(SnapshotStore(rows), KlineStore())
    result = evaluator.evaluate("USD_M", "BTCUSDT", "1h", "1h", 10)
    walk = result["horizons"]["1"]["walk_forward"]
    assert walk["status"] == "COMPLETED"
    assert walk["fold_count"] == 3
    assert [fold["training_snapshot_count"] for fold in walk["folds"]] == [3, 4, 5]
    assert [fold["test_snapshot_count"] for fold in walk["folds"]] == [1, 1, 1]
    test_ids = [snapshot_id for fold in walk["folds"] for snapshot_id in fold["test_snapshot_ids"]]
    assert test_ids == ["wf-4", "wf-5", "wf-6"]
    assert walk["test_snapshot_count"] == 3
    assert walk["test_directional_sample_size"] <= walk["test_matured_outcome_count"]


def test_walk_forward_requires_four_snapshots():
    evaluator = MarketConfluencePerformance(
        SnapshotStore([snapshot("BULLISH"), snapshot("BEARISH"), snapshot("MIXED")]),
        KlineStore(),
    )
    result = evaluator.evaluate("USD_M", "BTCUSDT", "1h", "1h", 10)
    walk = result["horizons"]["1"]["walk_forward"]
    assert walk["status"] == "INSUFFICIENT_SNAPSHOTS"
    assert walk["fold_count"] == 0
    assert walk["test_directional_positive_fraction"] is None


def test_wilson_interval_and_minimum_sample_warning_are_reported():
    from app.services.market_confluence_performance import _directional_statistics

    small = _directional_statistics([
        {"directional_positive": True},
        {"directional_positive": False},
    ])
    assert small["positive_fraction"] == 0.5
    assert small["sample_size_status"] == "LOW_SAMPLE_SIZE"
    assert small["minimum_sample_size"] == 30
    interval = small["positive_fraction_ci_95_wilson"]
    assert interval["method"] == "Wilson score interval, nominal 95%"
    assert 0.09 < interval["lower"] < 0.10
    assert 0.90 < interval["upper"] < 0.91

    adequate = _directional_statistics(
        [{"directional_positive": index < 15} for index in range(30)]
    )
    assert adequate["sample_size_status"] == "SAMPLE_SIZE_AT_LEAST_30"


def test_zero_directional_samples_have_no_confidence_interval():
    from app.services.market_confluence_performance import _directional_statistics

    result = _directional_statistics([])
    assert result["sample_size_status"] == "NO_DIRECTIONAL_SAMPLES"
    assert result["positive_fraction"] is None
    assert result["positive_fraction_ci_95_wilson"] is None


def test_walk_forward_and_holdout_include_wilson_intervals():
    rows = []
    for index, bias in enumerate(
        ["BULLISH", "BULLISH", "BEARISH", "BEARISH", "BULLISH", "BEARISH"], start=1
    ):
        item = snapshot(bias)
        item["snapshot_id"] = f"ci-{index}"
        item["analyzed_at_ms"] = index * 1_000_000
        rows.append(item)
    result = MarketConfluencePerformance(SnapshotStore(rows), KlineStore()).evaluate(
        "USD_M", "BTCUSDT", "1h", "1h", 10
    )
    horizon = result["horizons"]["1"]
    assert horizon["walk_forward"]["test_directional_positive_fraction_ci_95_wilson"] is not None
    assert horizon["walk_forward"]["sample_size_status"] == "LOW_SAMPLE_SIZE"
    assert horizon["out_of_sample"]["test_directional_positive_fraction_ci_95_wilson"] is not None


def test_non_overlapping_selector_keeps_maximum_non_overlapping_outcome_windows():
    from app.services.market_confluence_performance import _non_overlapping_rows

    rows = [
        {"snapshot_id": "long", "analyzed_at_ms": 0, "outcome_close_time_ms": 100,
         "directional_positive": True},
        {"snapshot_id": "short-a", "analyzed_at_ms": 1, "outcome_close_time_ms": 40,
         "directional_positive": False},
        {"snapshot_id": "short-b", "analyzed_at_ms": 41, "outcome_close_time_ms": 80,
         "directional_positive": True},
        {"snapshot_id": "short-c", "analyzed_at_ms": 81, "outcome_close_time_ms": 120,
         "directional_positive": False},
    ]
    selected = _non_overlapping_rows(rows)
    assert [row["snapshot_id"] for row in selected] == ["short-a", "short-b", "short-c"]
    assert all(
        selected[index]["analyzed_at_ms"] > selected[index - 1]["outcome_close_time_ms"]
        for index in range(1, len(selected))
    )


def test_performance_reports_raw_and_non_overlapping_statistics():
    rows = []
    for index, bias in enumerate(
        ["BULLISH", "BEARISH", "BULLISH", "BEARISH", "BULLISH", "BEARISH"], start=1
    ):
        item = snapshot(bias)
        item["snapshot_id"] = f"overlap-{index}"
        item["analyzed_at_ms"] = index * 1_000_000
        rows.append(item)
    result = MarketConfluencePerformance(SnapshotStore(rows), KlineStore()).evaluate(
        "USD_M", "BTCUSDT", "1h", "1h", 10
    )
    horizon = result["horizons"]["1"]
    adjusted = horizon["dependence_adjusted"]
    assert adjusted["directional_sample_size"] <= horizon["directional_sample_size"]
    assert adjusted["overlap_excluded_count"] == (
        horizon["directional_sample_size"] - adjusted["directional_sample_size"]
    )
    assert "non_overlapping_directional_sample_size" in horizon["walk_forward"]
    assert "non_overlapping_directional_sample_size" in horizon["out_of_sample"]


def test_regime_bias_breakdown_reports_confidence_and_overlap_reliability():
    rows = []
    for index, bias in enumerate(
        ["BULLISH", "BEARISH", "BULLISH", "BEARISH", "BULLISH", "BEARISH"],
        start=1,
    ):
        item = snapshot(bias)
        item["snapshot_id"] = f"reliability-{index}"
        item["analyzed_at_ms"] = index * 1_000_000
        item["payload"] = {"evidence": [{
            "source": "MARKET_REGIME",
            "detail": {"regime": "TREND"},
        }]}
        rows.append(item)

    result = MarketConfluencePerformance(
        SnapshotStore(rows), KlineStore(),
    ).evaluate("USD_M", "BTCUSDT", "1h", "1h", 10)
    group = result["horizons"]["1"]["regime_bias_breakdown"]["market_regime"]["TREND"]["BULLISH"]

    assert group["sample_size"] == 3
    assert group["directional_sample_size"] == 3
    assert group["positive_fraction"] == 1.0
    assert group["positive_fraction_ci_95_wilson"]["method"] == "Wilson score interval, nominal 95%"
    assert group["minimum_directional_sample_size"] == 30
    assert group["sample_size_status"] == "LOW_SAMPLE_SIZE"
    assert group["non_overlapping_directional_sample_size"] <= group["directional_sample_size"]
    assert group["overlap_excluded_count"] == (
        group["directional_sample_size"] - group["non_overlapping_directional_sample_size"]
    )
