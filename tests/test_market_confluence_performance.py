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
    assert walk["consistency_assessment"]["status"] == "INSUFFICIENT_FOLD_EVIDENCE"
    assert walk["consistency_assessment"]["eligible_fold_count"] == 0
    assert walk["consistency_assessment"]["insufficient_fold_count"] == 3
    comparison = result["horizons"]["1"]["historical_vs_walk_forward"]
    assert comparison["status"] == "LOW_SAMPLE_SIZE"
    assert comparison["historical_directional_sample_size"] >= 0
    assert comparison["walk_forward_test_directional_sample_size"] < 30
    assert comparison["positive_fraction_difference_percentage_points"] is not None


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
            "detail": {
                "regime": "TREND",
                "volatility_regime": "HIGH",
                "structure_regime": "EXPANSION",
            },
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


def test_regime_bias_alignment_breakdown_separates_alignment_groups():
    rows = []
    specifications = [
        ("BULLISH", "ALIGNED"),
        ("BULLISH", "ALIGNED"),
        ("BULLISH", "CONFLICTING"),
        ("BEARISH", "ALIGNED"),
        ("BEARISH", "CONFLICTING"),
        ("BEARISH", "CONFLICTING"),
    ]
    for index, (bias, alignment) in enumerate(specifications, start=1):
        item = snapshot(bias)
        item["snapshot_id"] = f"alignment-{index}"
        item["analyzed_at_ms"] = index * 1_000_000
        item["alignment"] = alignment
        item["payload"] = {"evidence": [{
            "source": "MARKET_REGIME",
            "detail": {
                "regime": "TREND",
                "volatility_regime": "HIGH",
                "structure_regime": "EXPANSION",
            },
        }]}
        rows.append(item)

    result = MarketConfluencePerformance(
        SnapshotStore(rows), KlineStore(),
    ).evaluate("USD_M", "BTCUSDT", "1h", "1h", 10)
    grouped = result["horizons"]["1"]["regime_bias_alignment_breakdown"]["market_regime"]["TREND"]

    assert grouped["BULLISH"]["ALIGNED"]["sample_size"] == 2
    assert grouped["BULLISH"]["CONFLICTING"]["sample_size"] == 1
    assert grouped["BEARISH"]["ALIGNED"]["sample_size"] == 1
    assert grouped["BEARISH"]["CONFLICTING"]["sample_size"] == 2
    assert grouped["BULLISH"]["ALIGNED"]["positive_fraction"] == 1.0
    assert grouped["BULLISH"]["ALIGNED"]["sample_size_status"] == "LOW_SAMPLE_SIZE"
    assert grouped["BULLISH"]["ALIGNED"]["positive_fraction_ci_95_wilson"] is not None

    volatility = result["horizons"]["1"]["regime_bias_alignment_breakdown"]["volatility_regime"]["HIGH"]
    structure = result["horizons"]["1"]["regime_bias_alignment_breakdown"]["structure_regime"]["EXPANSION"]
    assert volatility["BULLISH"]["ALIGNED"]["sample_size"] == 2
    assert volatility["BEARISH"]["CONFLICTING"]["sample_size"] == 2
    assert structure["BULLISH"]["CONFLICTING"]["sample_size"] == 1
    assert structure["BEARISH"]["ALIGNED"]["sample_size"] == 1

def test_horizon_comparison_ranks_only_metrics_with_at_least_30_samples():
    rows = []
    for index in range(30):
        item = snapshot("BULLISH")
        item["snapshot_id"] = f"ranking-{index}"
        item["analyzed_at_ms"] = index * 7_200_000
        rows.append(item)

    result = MarketConfluencePerformance(
        SnapshotStore(rows), KlineStore(),
    ).evaluate("USD_M", "BTCUSDT", "1h", "1h", 50)

    signal_quality = result["horizons"]["1"]["signal_quality"]
    assert signal_quality["prediction_sample_size"] == 30
    assert signal_quality["status"] in {"LOW_SAMPLE_SIZE", "DESCRIPTIVE_CLASSIFICATION_METRICS"}
    assert signal_quality["confusion_matrix"]["true_positive"] + signal_quality["confusion_matrix"]["false_positive"] == 30
    assert set(result["horizons"]["1"]["signal_quality_by_regime"]) == {
        "market_regime", "volatility_regime", "structure_regime",
    }

    comparison = result["horizon_comparison"]
    assert comparison["status"] == "DESCRIPTIVE_ONLY"
    assert comparison["minimum_sample_size"] == 30

    positive = comparison["rankings"]["directional_positive_fraction"]
    assert positive["minimum_sample_size"] == 30
    one_hour = next(row for row in positive["ranked"] if row["horizon_hours"] == 1)
    assert one_hour["rank"] == 1
    assert one_hour["sample_size"] == 30
    assert one_hour["value"] == 1.0
    assert all(row["sample_size"] >= 30 for row in positive["ranked"])
    assert all(row["reason"] == "BELOW_MINIMUM_SAMPLE_SIZE" for row in positive["excluded"])

    non_overlap = comparison["rankings"]["non_overlapping_positive_fraction"]
    assert all(row["sample_size"] >= 30 for row in non_overlap["ranked"])
    assert "composite score" in comparison["method"]

    leaderboard = result["historical_leaderboard"]
    assert leaderboard["status"] == "DESCRIPTIVE_ONLY"
    market_one_hour = leaderboard["dimensions"]["market_regime"]["1"]
    positive_groups = market_one_hour["rankings"]["positive_fraction"]
    group = next(row for row in positive_groups["ranked"] if row["bias"] == "BULLISH")
    assert group["sample_size"] == 30
    assert group["rank"] == 1
    assessment = group["reliability_assessment"]
    assert assessment["classification"] == "INTERVAL_ABOVE_50_PERCENT"
    assert assessment["directional_sample_size"] == 30
    assert assessment["positive_fraction_ci_95_wilson_width"] is not None
    assert assessment["coverage_complete_fraction"] == 0.0
    assert assessment["overlap_sensitivity_absolute_gap"] is not None
    assert market_one_hour["reliability_summary"]["group_count"] >= 1
    assert all(row["sample_size"] >= 30 for row in positive_groups["ranked"])
    assert all(row["reason"] == "BELOW_MINIMUM_SAMPLE_SIZE" for row in positive_groups["excluded"])
    assert "not a forecast" in leaderboard["method"]


def test_walk_forward_consistency_uses_only_folds_with_minimum_samples():
    from app.services.market_confluence_performance import _walk_forward_consistency

    def fold(sample_size, fraction, lower, upper):
        return {
            "test_directional_sample_size": sample_size,
            "test_directional_positive_fraction": fraction,
            "test_directional_positive_fraction_ci_95_wilson": {
                "lower": lower, "upper": upper,
            },
        }

    result = _walk_forward_consistency([
        fold(30, 0.7, 0.53, 0.83),
        fold(30, 0.3, 0.17, 0.47),
        fold(30, 0.5, 0.33, 0.67),
        fold(12, 1.0, 0.76, 1.0),
    ])
    assert result["status"] == "MIXED_DIRECTIONAL_RESULTS"
    assert result["total_fold_count"] == 4
    assert result["eligible_fold_count"] == 3
    assert result["insufficient_fold_count"] == 1
    assert result["folds_above_50_percent_point_estimate"] == 1
    assert result["folds_at_or_below_50_percent_point_estimate"] == 2
    assert result["folds_with_interval_above_50_percent"] == 1
    assert result["folds_with_interval_below_50_percent"] == 1
    assert result["folds_with_interval_including_50_percent"] == 1
    assert abs(result["positive_fraction_range"] - 0.4) < 1e-9


def test_historical_walk_forward_comparison_reports_interval_overlap_and_sample_gating():
    from app.services.market_confluence_performance import _historical_walk_forward_comparison

    historical = {
        "directional_sample_size": 100,
        "directional_positive_fraction": 0.60,
        "directional_positive_fraction_ci_95_wilson": {"lower": 0.50, "upper": 0.69},
        "mean_directional_return_percent": 0.25,
    }
    walk_forward = {
        "test_directional_sample_size": 45,
        "test_directional_positive_fraction": 0.56,
        "test_directional_positive_fraction_ci_95_wilson": {"lower": 0.41, "upper": 0.70},
        "test_mean_directional_return_percent": 0.10,
    }
    result = _historical_walk_forward_comparison(historical, walk_forward)
    assert result["status"] == "NOMINAL_INTERVALS_OVERLAP"
    assert result["nominal_confidence_intervals_overlap"] is True
    assert result["positive_fraction_difference_percentage_points"] < 0
    assert abs(result["mean_directional_return_difference_percentage_points"] + 0.15) < 1e-9
    assert "not a formal significance test" in result["interpretation"]

    walk_forward["test_directional_sample_size"] = 12
    low_sample = _historical_walk_forward_comparison(historical, walk_forward)
    assert low_sample["status"] == "LOW_SAMPLE_SIZE"


def test_data_quality_risk_assessment_flags_weak_coverage_overlap_and_selection_risk():
    from app.services.market_confluence_performance import _data_quality_risk_assessment

    assessment = _data_quality_risk_assessment({
        "sample_size": 40,
        "directional_sample_size": 36,
        "coverage_complete_count": 30,
        "coverage_partial_count": 10,
        "dependence_adjusted": {"overlap_excluded_count": 20},
        "walk_forward": {
            "consistency_assessment": {
                "eligible_fold_count": 1,
                "total_fold_count": 3,
                "status": "MIXED_DIRECTIONAL_RESULTS",
            },
        },
        "historical_vs_walk_forward": {
            "status": "NOMINAL_INTERVALS_DO_NOT_OVERLAP",
        },
    })
    codes = {flag["code"] for flag in assessment["flags"]}
    assert assessment["status"] == "WARNINGS_PRESENT"
    assert assessment["coverage_complete_fraction"] == 0.75
    assert assessment["overlap_excluded_fraction_of_directional"] == 20 / 36
    assert {
        "INCOMPLETE_FUTURE_CANDLE_COVERAGE",
        "OVERLAPPING_OUTCOME_WINDOWS",
        "INSUFFICIENT_WALK_FORWARD_FOLD_SAMPLES",
        "MIXED_WALK_FORWARD_FOLD_RESULTS",
        "HISTORICAL_AND_WALK_FORWARD_INTERVALS_DIFFER",
    }.issubset(codes)
    assert assessment["overfitting_assessment"]["status"] == "NOT_DIRECTLY_TESTED"
    assert assessment["overfitting_assessment"]["selection_bias_risk"] == "PRESENT_WHEN_SELECTING_TOP_GROUPS"


def test_data_quality_risk_assessment_marks_small_samples_and_does_not_claim_clean_data():
    from app.services.market_confluence_performance import _data_quality_risk_assessment

    assessment = _data_quality_risk_assessment({
        "sample_size": 5,
        "directional_sample_size": 4,
        "coverage_complete_count": 5,
        "coverage_partial_count": 0,
        "dependence_adjusted": {"overlap_excluded_count": 0},
        "walk_forward": {"consistency_assessment": {
            "eligible_fold_count": 0, "total_fold_count": 0,
            "status": "INSUFFICIENT_FOLD_EVIDENCE",
        }},
        "historical_vs_walk_forward": {"status": "LOW_SAMPLE_SIZE"},
    })
    assert assessment["status"] == "WARNINGS_PRESENT"
    assert assessment["flags"][0]["code"] == "LOW_DIRECTIONAL_SAMPLE_SIZE"
    assert assessment["overfitting_assessment"]["status"] == "NOT_DIRECTLY_TESTED"


def test_signal_quality_assessment_confusion_matrix_and_flat_outcome_handling():
    from app.services.market_confluence_performance import _signal_quality_assessment

    rows = [
        {"bias": "BULLISH", "market_return_percent": 2.0},
        {"bias": "BULLISH", "market_return_percent": -1.0},
        {"bias": "BEARISH", "market_return_percent": -3.0},
        {"bias": "BEARISH", "market_return_percent": 1.0},
        {"bias": "BULLISH", "market_return_percent": 0.0},
        {"bias": "MIXED", "market_return_percent": 4.0},
    ]
    result = _signal_quality_assessment(rows)
    assert result["status"] == "LOW_SAMPLE_SIZE"
    assert result["prediction_sample_size"] == 5
    assert result["scored_non_flat_sample_size"] == 4
    assert result["flat_outcome_count"] == 1
    assert result["confusion_matrix"] == {
        "true_positive": 1, "false_positive": 1,
        "true_negative": 1, "false_negative": 1,
    }
    assert result["accuracy"] == 0.5
    assert result["precision"] == 0.5
    assert result["recall"] == 0.5
    assert result["specificity"] == 0.5
    assert result["f1_score"] == 0.5
    assert result["accuracy_ci_95_wilson"] is not None
    assert "periods with no call" in result["interpretation"]


def test_signal_quality_assessment_withholds_metrics_without_bullish_or_bearish_calls():
    from app.services.market_confluence_performance import _signal_quality_assessment

    result = _signal_quality_assessment([
        {"bias": "MIXED", "market_return_percent": 1.0},
        {"bias": "UNKNOWN", "market_return_percent": -1.0},
    ])
    assert result["status"] == "NO_DIRECTIONAL_CALLS"
    assert result["prediction_sample_size"] == 0
    assert result["accuracy"] is None
    assert result["confusion_matrix"]["false_positive"] == 0


def test_out_of_sample_regime_stability_reports_each_saved_regime_dimension():
    from app.services.market_confluence_performance import _out_of_sample_regime_stability

    rows = [
        {
            "market_regime": "TREND", "volatility_regime": "HIGH",
            "structure_regime": "EXPANSION", "directional_positive": True,
            "directional_return_percent": 1.5, "future_candle_coverage_complete": True,
        },
        {
            "market_regime": "TREND", "volatility_regime": "HIGH",
            "structure_regime": "EXPANSION", "directional_positive": False,
            "directional_return_percent": -0.5, "future_candle_coverage_complete": False,
        },
        {
            "market_regime": "RANGE", "volatility_regime": "LOW",
            "structure_regime": "COMPRESSION", "directional_positive": True,
            "directional_return_percent": 0.7, "future_candle_coverage_complete": True,
        },
    ]
    result = _out_of_sample_regime_stability(rows)
    assert result["status"] == "COMPLETED"
    assert result["minimum_directional_sample_size_reporting_threshold"] == 30
    trend = result["dimensions"]["market_regime"]["TREND"]
    assert trend["sample_size"] == 2
    assert trend["directional_sample_size"] == 2
    assert trend["positive_fraction"] == 0.5
    assert trend["sample_size_status"] == "LOW_SAMPLE_SIZE"
    assert trend["coverage_complete_fraction"] == 0.5
    assert result["dimensions"]["volatility_regime"]["HIGH"]["directional_sample_size"] == 2
    assert result["dimensions"]["structure_regime"]["EXPANSION"]["positive_count"] == 1


def test_out_of_sample_training_outcomes_are_purged_at_holdout_boundary():
    rows = []
    for index in range(10):
        item = snapshot("BULLISH")
        item["snapshot_id"] = f"purge-{index}"
        item["analyzed_at_ms"] = index * 3_600_000
        rows.append(item)

    class BoundaryKlineStore:
        def history(self, market, symbol, interval, start_time_ms, end_time_ms, limit):
            close_time = end_time_ms - 3_600_000
            return {"candles": [{
                "open_time_ms": start_time_ms,
                "close_time_ms": close_time,
                "high": 102.0, "low": 98.0, "close": 101.0,
            }]}

    result = MarketConfluencePerformance(
        SnapshotStore(rows), BoundaryKlineStore(),
    ).evaluate("USD_M", "BTCUSDT", "1h", "1h", 20)
    holdout = result["horizons"]["1"]["out_of_sample"]
    assert holdout["training_snapshot_count"] == 7
    assert holdout["test_snapshot_count"] == 3
    assert holdout["training_purged_overlap_count"] == 7
    assert holdout["training_matured_outcome_count"] == 0
    assert holdout["test_regime_stability"]["status"] == "COMPLETED"
    assert set(holdout["test_regime_stability"]["dimensions"]) == {
        "market_regime", "volatility_regime", "structure_regime",
    }
