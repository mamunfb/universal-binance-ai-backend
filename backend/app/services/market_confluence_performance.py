from __future__ import annotations

import math
from typing import Any

from app.services.historical_klines import HistoricalKlineStore
from app.services.market_confluence_store import MarketConfluenceStore


def _snapshot_regime_labels(snapshot: dict[str, Any]) -> dict[str, str]:
    """Read regime labels from saved MARKET_REGIME evidence without guessing."""
    payload = snapshot.get("payload") or {}
    evidence = payload.get("evidence") or []
    item = next((entry for entry in evidence if entry.get("source") == "MARKET_REGIME"), {})
    detail = item.get("detail") or {}
    keys = {"market_regime": "regime", "volatility_regime": "volatility_regime",
            "structure_regime": "structure_regime"}
    return {name: (str(detail.get(source)).strip().upper()
                   if detail.get(source) is not None and str(detail.get(source)).strip()
                   else "UNCLASSIFIED") for name, source in keys.items()}



def _directional_statistics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Return a nominal 95% Wilson interval and a transparent small-sample flag."""
    sample_size = len(rows)
    positive_count = sum(bool(row["directional_positive"]) for row in rows)
    minimum_sample_size = 30  # Reporting threshold only; never filters observations.
    if sample_size == 0:
        return {
            "positive_count": 0, "negative_count": 0, "positive_fraction": None,
            "positive_fraction_ci_95_wilson": None,
            "minimum_sample_size": minimum_sample_size,
            "sample_size_status": "NO_DIRECTIONAL_SAMPLES",
        }
    fraction = positive_count / sample_size
    z = 1.96
    z_squared = z * z
    denominator = 1.0 + z_squared / sample_size
    center = (fraction + z_squared / (2.0 * sample_size)) / denominator
    margin = z * math.sqrt(
        fraction * (1.0 - fraction) / sample_size
        + z_squared / (4.0 * sample_size * sample_size)
    ) / denominator
    return {
        "positive_count": positive_count,
        "negative_count": sample_size - positive_count,
        "positive_fraction": fraction,
        "positive_fraction_ci_95_wilson": {
            "lower": max(0.0, center - margin),
            "upper": min(1.0, center + margin),
            "method": "Wilson score interval, nominal 95%",
        },
        "minimum_sample_size": minimum_sample_size,
        "sample_size_status": "SAMPLE_SIZE_AT_LEAST_30" if sample_size >= minimum_sample_size else "LOW_SAMPLE_SIZE",
    }



def _out_of_sample_regime_stability(
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Describe untouched chronological holdout outcomes within each saved regime label."""
    dimensions = ("market_regime", "volatility_regime", "structure_regime")
    result: dict[str, Any] = {
        "status": "COMPLETED" if rows else "NO_HOLDOUT_OUTCOMES",
        "method": (
            "Groups only chronological holdout outcomes by regime labels saved at signal time. "
            "No regime labels are inferred from future prices. Groups with fewer than 30 directional "
            "outcomes are reported but flagged as low sample."
        ),
        "minimum_directional_sample_size_reporting_threshold": 30,
        "dimensions": {},
    }
    for dimension in dimensions:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            grouped.setdefault(str(row.get(dimension) or "UNCLASSIFIED"), []).append(row)
        result["dimensions"][dimension] = {}
        for label, group_rows in sorted(grouped.items()):
            directional = [
                row for row in group_rows
                if row.get("directional_positive") is not None
                and row.get("directional_return_percent") is not None
            ]
            stats = _directional_statistics(directional)
            sample_size = len(directional)
            result["dimensions"][dimension][label] = {
                "sample_size": len(group_rows),
                "directional_sample_size": sample_size,
                "positive_count": stats["positive_count"],
                "negative_count": stats["negative_count"],
                "positive_fraction": stats["positive_fraction"],
                "positive_fraction_ci_95_wilson": stats["positive_fraction_ci_95_wilson"],
                "sample_size_status": stats["sample_size_status"],
                "mean_directional_return_percent": (
                    sum(float(row["directional_return_percent"]) for row in directional) / sample_size
                    if sample_size else None
                ),
                "coverage_complete_count": sum(
                    bool(row.get("future_candle_coverage_complete")) for row in group_rows
                ),
                "coverage_complete_fraction": (
                    sum(bool(row.get("future_candle_coverage_complete")) for row in group_rows) / len(group_rows)
                    if group_rows else None
                ),
            }
    return result


def _regime_transition_degradation(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Screen chronological holdout halves for within-regime directional degradation."""
    ordered = sorted(rows, key=lambda row: int(row.get("analyzed_at_ms") or 0))
    timestamps = sorted({int(row.get("analyzed_at_ms") or 0) for row in ordered})
    split_index = len(timestamps) // 2
    split_timestamp = timestamps[split_index] if split_index < len(timestamps) else None
    early = [row for row in ordered if split_timestamp is not None and int(row.get("analyzed_at_ms") or 0) < split_timestamp]
    late = [row for row in ordered if split_timestamp is not None and int(row.get("analyzed_at_ms") or 0) >= split_timestamp]
    threshold_pp = 10.0
    minimum_n = 30

    def metrics(group: list[dict[str, Any]]) -> dict[str, Any]:
        directional = [
            row for row in group
            if row.get("directional_positive") is not None
            and row.get("directional_return_percent") is not None
        ]
        stats = _directional_statistics(directional)
        return {
            "sample_size": len(group),
            "directional_sample_size": len(directional),
            "positive_fraction": stats["positive_fraction"],
            "positive_fraction_ci_95_wilson": stats["positive_fraction_ci_95_wilson"],
            "mean_directional_return_percent": (
                sum(float(row["directional_return_percent"]) for row in directional) / len(directional)
                if directional else None
            ),
        }

    output: dict[str, Any] = {
        "status": "COMPLETED" if split_timestamp is not None else "INSUFFICIENT_HOLDOUT_PERIODS",
        "method": (
            "Chronological holdout outcomes split into early and late halves by unique signal timestamp. "
            "Within each saved regime label, positive-fraction change is late minus early. "
            "A decline of at least 10 percentage points is a screening heuristic only, not a statistical "
            "test, proof of regime causality, or evidence of model overfitting."
        ),
        "split_timestamp_ms": split_timestamp,
        "minimum_directional_sample_size_per_period": minimum_n,
        "degradation_screen_threshold_percentage_points": threshold_pp,
        "overall": {},
        "dimensions": {},
    }
    overall_early = metrics(early)
    overall_late = metrics(late)
    output["overall"] = _degradation_comparison(overall_early, overall_late, minimum_n, threshold_pp)
    for dimension in ("market_regime", "volatility_regime", "structure_regime"):
        labels = sorted({str(row.get(dimension) or "UNCLASSIFIED") for row in ordered})
        output["dimensions"][dimension] = {}
        for label in labels:
            group = [row for row in ordered if str(row.get(dimension) or "UNCLASSIFIED") == label]
            group_early = [row for row in group if split_timestamp is not None and int(row.get("analyzed_at_ms") or 0) < split_timestamp]
            group_late = [row for row in group if split_timestamp is not None and int(row.get("analyzed_at_ms") or 0) >= split_timestamp]
            output["dimensions"][dimension][label] = _degradation_comparison(
                metrics(group_early), metrics(group_late), minimum_n, threshold_pp
            )
    return output


def _degradation_comparison(
    early: dict[str, Any], late: dict[str, Any], minimum_n: int, threshold_pp: float,
) -> dict[str, Any]:
    early_n = int(early["directional_sample_size"])
    late_n = int(late["directional_sample_size"])
    early_fraction = early["positive_fraction"]
    late_fraction = late["positive_fraction"]
    difference_pp = (
        (late_fraction - early_fraction) * 100
        if early_fraction is not None and late_fraction is not None else None
    )
    status = (
        "INSUFFICIENT_PERIOD_SAMPLES" if early_n < minimum_n or late_n < minimum_n
        else "POTENTIAL_DEGRADATION_SCREEN" if difference_pp is not None and difference_pp <= -threshold_pp
        else "NO_DEGRADATION_THRESHOLD_CROSSED"
    )
    return {
        "status": status,
        "early": early,
        "late": late,
        "positive_fraction_change_percentage_points": difference_pp,
        "threshold_percentage_points": threshold_pp,
        "minimum_directional_sample_size_per_period": minimum_n,
    }


def _regime_transition_analysis(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Detect saved regime-label transitions and compare matured outcomes around each change."""
    dimensions = ("market_regime", "volatility_regime", "structure_regime")
    minimum_n = 30
    threshold_pp = 10.0
    ordered = sorted(rows, key=lambda row: int(row.get("analyzed_at_ms") or 0))
    result: dict[str, Any] = {
        "status": "COMPLETED" if ordered else "NO_MATURED_HOLDOUT_OUTCOMES",
        "method": (
            "Transitions are changes between consecutive regime labels saved with matured holdout snapshots. "
            "For each transition, pre-transition outcomes are retained only when their outcome close time is "
            "strictly before the transition timestamp; post-transition outcomes are snapshots in the new "
            "regime segment. This is descriptive and does not establish that the regime change caused any "
            "performance change. Immature snapshots are not represented."
        ),
        "minimum_directional_sample_size_per_side": minimum_n,
        "degradation_screen_threshold_percentage_points": threshold_pp,
        "dimensions": {},
    }

    def summarize(group: list[dict[str, Any]]) -> dict[str, Any]:
        directional = [
            row for row in group
            if row.get("directional_positive") is not None
            and row.get("directional_return_percent") is not None
        ]
        stats = _directional_statistics(directional)
        return {
            "snapshot_sample_size": len(group),
            "directional_sample_size": len(directional),
            "positive_fraction": stats["positive_fraction"],
            "positive_fraction_ci_95_wilson": stats["positive_fraction_ci_95_wilson"],
            "mean_directional_return_percent": (
                sum(float(row["directional_return_percent"]) for row in directional) / len(directional)
                if directional else None
            ),
        }

    for dimension in dimensions:
        points = []
        seen_timestamps = set()
        for row in ordered:
            timestamp = int(row.get("analyzed_at_ms") or 0)
            if timestamp in seen_timestamps:
                continue
            seen_timestamps.add(timestamp)
            points.append((timestamp, str(row.get(dimension) or "UNCLASSIFIED")))
        segments: list[dict[str, Any]] = []
        for timestamp, label in points:
            if not segments or segments[-1]["label"] != label:
                segments.append({"label": label, "start_timestamp_ms": timestamp, "rows": []})
            segments[-1]["rows"].extend(
                row for row in ordered
                if int(row.get("analyzed_at_ms") or 0) == timestamp
            )
        transitions = []
        for index in range(1, len(segments)):
            previous = segments[index - 1]
            current = segments[index]
            transition_time = current["start_timestamp_ms"]
            pre_rows = [
                row for row in previous["rows"]
                if int(row.get("outcome_close_time_ms") or 0) < transition_time
            ]
            post_rows = current["rows"]
            pre = summarize(pre_rows)
            post = summarize(post_rows)
            pre_n = pre["directional_sample_size"]
            post_n = post["directional_sample_size"]
            difference_pp = (
                (post["positive_fraction"] - pre["positive_fraction"]) * 100
                if pre["positive_fraction"] is not None and post["positive_fraction"] is not None
                else None
            )
            if pre_n < minimum_n or post_n < minimum_n:
                status = "INSUFFICIENT_TRANSITION_SAMPLES"
                adaptation_status = "UNVALIDATED"
            elif difference_pp is not None and difference_pp <= -threshold_pp:
                status = "POTENTIAL_POST_TRANSITION_DEGRADATION"
                adaptation_status = "MANUAL_REVIEW_ONLY"
            else:
                status = "NO_DEGRADATION_THRESHOLD_CROSSED"
                adaptation_status = "MANUAL_REVIEW_ONLY"
            transitions.append({
                "from_regime": previous["label"],
                "to_regime": current["label"],
                "transition_timestamp_ms": transition_time,
                "pre_transition": pre,
                "post_transition": post,
                "positive_fraction_change_percentage_points": difference_pp,
                "status": status,
                "signal_adaptation_status": adaptation_status,
            })
        latest = segments[-1] if segments else None
        latest_stats = summarize(latest["rows"]) if latest else summarize([])
        result["dimensions"][dimension] = {
            "transition_count": len(transitions),
            "latest_observed_regime": latest["label"] if latest else None,
            "latest_regime_sample": latest_stats,
            "latest_regime_sample_status": (
                "SUFFICIENT_FOR_SCREENING_THRESHOLD"
                if latest_stats["directional_sample_size"] >= minimum_n
                else "INSUFFICIENT_FOR_SCREENING"
            ),
            "transitions": transitions,
        }
    return result


def _signal_quality_assessment(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Evaluate explicit bullish/bearish confluence calls as an UP-vs-DOWN classifier."""
    eligible = [
        row for row in rows
        if row.get("bias") in {"BULLISH", "BEARISH"}
        and row.get("market_return_percent") is not None
    ]
    tp = fp = tn = fn = flat = 0
    for row in eligible:
        actual = float(row["market_return_percent"])
        if actual == 0:
            flat += 1
        elif row["bias"] == "BULLISH":
            tp += int(actual > 0)
            fp += int(actual < 0)
        else:
            fn += int(actual > 0)
            tn += int(actual < 0)
    scored = tp + fp + tn + fn

    def ratio(numerator: int, denominator: int) -> float | None:
        return numerator / denominator if denominator else None

    def ci(numerator: int, denominator: int) -> dict[str, float] | None:
        stats = _directional_statistics([
            {"directional_positive": index < numerator}
            for index in range(denominator)
        ])
        return stats["positive_fraction_ci_95_wilson"]

    accuracy_numerator = tp + tn
    precision_numerator = tp
    recall_numerator = tp
    specificity_numerator = tn
    accuracy = ratio(accuracy_numerator, scored)
    precision = ratio(precision_numerator, tp + fp)
    recall = ratio(recall_numerator, tp + fn)
    specificity = ratio(specificity_numerator, tn + fp)
    f1 = 2 * precision * recall / (precision + recall) if precision is not None and recall is not None and precision + recall else None
    sample_size = len(eligible)
    return {
        "status": (
            "NO_DIRECTIONAL_CALLS" if sample_size == 0
            else "LOW_SAMPLE_SIZE" if scored < 30
            else "DESCRIPTIVE_CLASSIFICATION_METRICS"
        ),
        "positive_class": "UPWARD_MARKET_RETURN",
        "negative_class": "DOWNWARD_MARKET_RETURN",
        "prediction_sample_size": sample_size,
        "scored_non_flat_sample_size": scored,
        "flat_outcome_count": flat,
        "confusion_matrix": {
            "true_positive": tp, "false_positive": fp,
            "true_negative": tn, "false_negative": fn,
        },
        "accuracy": accuracy,
        "accuracy_ci_95_wilson": ci(accuracy_numerator, scored),
        "precision": precision,
        "precision_ci_95_wilson": ci(precision_numerator, tp + fp),
        "recall": recall,
        "recall_ci_95_wilson": ci(recall_numerator, tp + fn),
        "specificity": specificity,
        "specificity_ci_95_wilson": ci(specificity_numerator, tn + fp),
        "f1_score": f1,
        "minimum_sample_size_reporting_threshold": 30,
        "interpretation": (
            "BULLISH predicts an upward close-to-close market return; BEARISH predicts a downward return. "
            "Flat returns are excluded from confusion-matrix metrics. False positives are bullish calls "
            "followed by negative returns; false negatives are bearish calls followed by positive returns. "
            "This evaluates only stored directional-call snapshots, not periods with no call, and does not "
            "adjust for overlapping observations or serial dependence. Wilson intervals are nominal."
        ),
    }


def _reliability_assessment(stats: dict[str, Any]) -> dict[str, Any]:
    """Expose transparent uncertainty diagnostics; this is not a predictive reliability score."""
    sample_size = int(stats.get("directional_sample_size") or 0)
    fraction = stats.get("positive_fraction")
    ci = stats.get("positive_fraction_ci_95_wilson")
    ci_width = float(ci["upper"]) - float(ci["lower"]) if ci is not None else None
    non_overlap_fraction = stats.get("non_overlapping_positive_fraction")
    overlap_gap = (
        abs(float(fraction) - float(non_overlap_fraction))
        if fraction is not None and non_overlap_fraction is not None else None
    )
    total = int(stats.get("sample_size") or 0)
    coverage_count = int(stats.get("coverage_complete_count") or 0)
    coverage_fraction = coverage_count / total if total else None
    if sample_size < 30 or ci is None or fraction is None:
        classification = "INSUFFICIENT_EVIDENCE"
    elif float(ci["lower"]) <= 0.5 <= float(ci["upper"]):
        classification = "INTERVAL_INCLUDES_50_PERCENT"
    elif float(ci["lower"]) > 0.5:
        classification = "INTERVAL_ABOVE_50_PERCENT"
    else:
        classification = "INTERVAL_BELOW_50_PERCENT"
    return {
        "classification": classification,
        "directional_sample_size": sample_size,
        "minimum_sample_size_reporting_threshold": 30,
        "positive_fraction_ci_95_wilson_width": ci_width,
        "overlap_sensitivity_absolute_gap": overlap_gap,
        "coverage_complete_fraction": coverage_fraction,
        "coverage_complete_count": coverage_count,
        "total_outcome_count": total,
        "interpretation": (
            "Descriptive diagnostics only. The nominal Wilson interval assumes independent observations "
            "and does not adjust for serial dependence; the 30-sample threshold is not a guarantee of adequacy."
        ),
    }


def _walk_forward_consistency(folds: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize direction consistency only across folds meeting the reporting threshold."""
    eligible = [
        fold for fold in folds
        if int(fold.get("test_directional_sample_size") or 0) >= 30
        and fold.get("test_directional_positive_fraction") is not None
        and fold.get("test_directional_positive_fraction_ci_95_wilson") is not None
    ]
    fractions = [float(fold["test_directional_positive_fraction"]) for fold in eligible]
    above = sum(value > 0.5 for value in fractions)
    at_or_below = len(fractions) - above
    interval_above = interval_below = interval_includes = 0
    for fold in eligible:
        ci = fold["test_directional_positive_fraction_ci_95_wilson"]
        if float(ci["lower"]) > 0.5:
            interval_above += 1
        elif float(ci["upper"]) < 0.5:
            interval_below += 1
        else:
            interval_includes += 1
    if not eligible:
        status = "INSUFFICIENT_FOLD_EVIDENCE"
    elif above == len(eligible):
        status = "ALL_ELIGIBLE_FOLDS_ABOVE_50_PERCENT"
    elif above == 0:
        status = "ALL_ELIGIBLE_FOLDS_AT_OR_BELOW_50_PERCENT"
    else:
        status = "MIXED_DIRECTIONAL_RESULTS"
    return {
        "status": status,
        "minimum_directional_sample_size_per_fold": 30,
        "total_fold_count": len(folds),
        "eligible_fold_count": len(eligible),
        "insufficient_fold_count": len(folds) - len(eligible),
        "folds_above_50_percent_point_estimate": above,
        "folds_at_or_below_50_percent_point_estimate": at_or_below,
        "folds_with_interval_above_50_percent": interval_above,
        "folds_with_interval_below_50_percent": interval_below,
        "folds_with_interval_including_50_percent": interval_includes,
        "minimum_fold_positive_fraction": min(fractions) if fractions else None,
        "maximum_fold_positive_fraction": max(fractions) if fractions else None,
        "positive_fraction_range": max(fractions) - min(fractions) if fractions else None,
        "interpretation": (
            "Descriptive consistency across eligible chronological test folds only. "
            "Folds below 30 directional observations are excluded; this threshold does not guarantee adequacy. "
            "Fold intervals are nominal Wilson intervals and do not adjust for dependence."
        ),
    }


def _historical_walk_forward_comparison(
    historical: dict[str, Any], walk_forward: dict[str, Any],
) -> dict[str, Any]:
    """Compare full-history descriptive results with chronological walk-forward test results."""
    historical_fraction = historical.get("directional_positive_fraction")
    walk_fraction = walk_forward.get("test_directional_positive_fraction")
    historical_n = int(historical.get("directional_sample_size") or 0)
    walk_n = int(walk_forward.get("test_directional_sample_size") or 0)
    historical_ci = historical.get("directional_positive_fraction_ci_95_wilson")
    walk_ci = walk_forward.get("test_directional_positive_fraction_ci_95_wilson")
    difference = (
        float(walk_fraction) - float(historical_fraction)
        if historical_fraction is not None and walk_fraction is not None else None
    )
    ci_overlap = None
    if historical_ci is not None and walk_ci is not None:
        ci_overlap = not (
            float(historical_ci["upper"]) < float(walk_ci["lower"])
            or float(walk_ci["upper"]) < float(historical_ci["lower"])
        )
    if historical_fraction is None or walk_fraction is None:
        status = "INSUFFICIENT_COMPARABLE_RESULTS"
    elif historical_n < 30 or walk_n < 30:
        status = "LOW_SAMPLE_SIZE"
    elif ci_overlap is None:
        status = "CONFIDENCE_INTERVAL_UNAVAILABLE"
    elif ci_overlap:
        status = "NOMINAL_INTERVALS_OVERLAP"
    else:
        status = "NOMINAL_INTERVALS_DO_NOT_OVERLAP"
    historical_mean = historical.get("mean_directional_return_percent")
    walk_mean = walk_forward.get("test_mean_directional_return_percent")
    return {
        "status": status,
        "comparison_basis": "Full-history descriptive outcomes versus the aggregate chronological walk-forward test folds.",
        "historical_directional_sample_size": historical_n,
        "walk_forward_test_directional_sample_size": walk_n,
        "historical_positive_fraction": historical_fraction,
        "historical_positive_fraction_ci_95_wilson": historical_ci,
        "walk_forward_positive_fraction": walk_fraction,
        "walk_forward_positive_fraction_ci_95_wilson": walk_ci,
        "walk_forward_minus_historical_positive_fraction": difference,
        "positive_fraction_difference_percentage_points": difference * 100.0 if difference is not None else None,
        "nominal_confidence_intervals_overlap": ci_overlap,
        "historical_mean_directional_return_percent": historical_mean,
        "walk_forward_mean_directional_return_percent": walk_mean,
        "mean_directional_return_difference_percentage_points": (
            float(walk_mean) - float(historical_mean)
            if historical_mean is not None and walk_mean is not None else None
        ),
        "interpretation": (
            "Descriptive comparison only: the full-history set includes earlier snapshots while walk-forward "
            "uses later chronological test folds. The samples are not independent, and interval overlap is "
            "not a formal significance test or evidence of predictive validity."
        ),
    }


def _data_quality_risk_assessment(horizon: dict[str, Any]) -> dict[str, Any]:
    """Surface observable data limitations without claiming to detect or quantify overfitting."""
    total = int(horizon.get("sample_size") or 0)
    directional_n = int(horizon.get("directional_sample_size") or 0)
    coverage_complete = int(horizon.get("coverage_complete_count") or 0)
    coverage_partial = int(horizon.get("coverage_partial_count") or 0)
    dependence = horizon.get("dependence_adjusted") or {}
    overlap_excluded = int(dependence.get("overlap_excluded_count") or 0)
    overlap_fraction = overlap_excluded / directional_n if directional_n else None
    walk = horizon.get("walk_forward") or {}
    consistency = walk.get("consistency_assessment") or {}
    comparison = horizon.get("historical_vs_walk_forward") or {}
    flags: list[dict[str, str]] = []

    if directional_n < 30:
        flags.append({
            "code": "LOW_DIRECTIONAL_SAMPLE_SIZE",
            "severity": "WARNING",
            "detail": f"Only {directional_n} directional outcomes; the reporting threshold is 30 and is not a guarantee of adequacy.",
        })
    if coverage_partial > 0:
        flags.append({
            "code": "INCOMPLETE_FUTURE_CANDLE_COVERAGE",
            "severity": "WARNING",
            "detail": f"{coverage_partial} of {total} matured outcomes do not have complete future-candle coverage.",
        })
    if overlap_excluded > 0:
        flags.append({
            "code": "OVERLAPPING_OUTCOME_WINDOWS",
            "severity": "WARNING",
            "detail": f"{overlap_excluded} of {directional_n} directional outcomes were excluded by the non-overlap selector ({(overlap_fraction or 0.0) * 100:.1f}%); this selector does not remove all serial dependence.",
        })
    if walk and int(consistency.get("eligible_fold_count") or 0) < int(consistency.get("total_fold_count") or 0):
        flags.append({
            "code": "INSUFFICIENT_WALK_FORWARD_FOLD_SAMPLES",
            "severity": "WARNING",
            "detail": f"Only {consistency.get('eligible_fold_count', 0)} of {consistency.get('total_fold_count', 0)} folds meet the per-fold directional sample threshold.",
        })
    if consistency.get("status") == "MIXED_DIRECTIONAL_RESULTS":
        flags.append({
            "code": "MIXED_WALK_FORWARD_FOLD_RESULTS",
            "severity": "WARNING",
            "detail": "Eligible chronological test folds do not all have positive fractions on the same side of 50%.",
        })
    if comparison.get("status") == "NOMINAL_INTERVALS_DO_NOT_OVERLAP":
        flags.append({
            "code": "HISTORICAL_AND_WALK_FORWARD_INTERVALS_DIFFER",
            "severity": "WARNING",
            "detail": "The nominal Wilson intervals do not overlap; this is a descriptive discrepancy, not a formal significance test.",
        })
    if not flags:
        flags.append({
            "code": "NO_TRIGGERED_DATA_QUALITY_FLAGS",
            "severity": "INFO",
            "detail": "No configured data-quality warning was triggered; this does not establish data quality or strategy validity.",
        })

    return {
        "status": "WARNINGS_PRESENT" if any(flag["severity"] == "WARNING" for flag in flags) else "NO_CONFIGURED_WARNING_TRIGGERED",
        "total_outcome_count": total,
        "directional_sample_size": directional_n,
        "coverage_complete_count": coverage_complete,
        "coverage_partial_count": coverage_partial,
        "coverage_complete_fraction": coverage_complete / total if total else None,
        "overlap_excluded_count": overlap_excluded,
        "overlap_excluded_fraction_of_directional": overlap_fraction,
        "flags": flags,
        "overfitting_assessment": {
            "status": "NOT_DIRECTLY_TESTED",
            "selection_bias_risk": "PRESENT_WHEN_SELECTING_TOP_GROUPS",
            "detail": (
                "This evaluator does not fit or tune a predictive model. Selecting apparently strong groups "
                "from many horizons, regimes, biases, and alignments can create selection bias; no multiple-"
                "comparison correction or independent confirmation set is implemented here."
            ),
        },
        "interpretation": (
            "Warnings describe observable sample, coverage, overlap, and fold limitations. They do not "
            "estimate the probability of overfitting and do not establish predictive performance."
        ),
    }



def _non_overlapping_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Select a maximum-cardinality set of non-overlapping forward outcome windows."""
    selected = []
    last_end = None
    # Earliest-finish interval scheduling gives a deterministic maximum-size subset.
    for row in sorted(
        rows,
        key=lambda item: (int(item["outcome_close_time_ms"]), int(item["analyzed_at_ms"])),
    ):
        start = int(row["analyzed_at_ms"])
        end = int(row["outcome_close_time_ms"])
        if end <= start:
            continue
        if last_end is None or start > last_end:
            selected.append(row)
            last_end = end
    return sorted(selected, key=lambda item: int(item["analyzed_at_ms"]))


class MarketConfluencePerformance:
    """Descriptive forward outcomes for saved snapshots, not a strategy backtest."""

    # 30 days is used as a fixed-length proxy for one month.
    HORIZONS_HOURS = (1, 4, 24, 48, 72, 360, 720)
    HORIZON_LABELS = {
        1: "1_hour", 4: "4_hours", 24: "24_hours", 48: "48_hours",
        72: "72_hours", 360: "15_days", 720: "30_days",
    }
    INTERVAL_MS = {
        "15m": 900_000, "30m": 1_800_000, "1h": 3_600_000,
        "2h": 7_200_000, "4h": 14_400_000, "6h": 21_600_000,
        "8h": 28_800_000, "12h": 43_200_000, "1d": 86_400_000,
    }

    def __init__(self, snapshots: MarketConfluenceStore, klines: HistoricalKlineStore) -> None:
        self.snapshots = snapshots
        self.klines = klines

    def evaluate(
        self, market: str, symbol: str, interval: str = "1h",
        price_interval: str = "1h", limit: int = 200,
    ) -> dict[str, Any]:
        if price_interval not in self.INTERVAL_MS:
            raise ValueError("price_interval must be 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, or 1d")
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")

        candle_step = self.INTERVAL_MS[price_interval]
        max_required = (max(self.HORIZONS_HOURS) * 3_600_000) // candle_step + 3
        if max_required > 5000:
            raise ValueError("Selected price_interval requires more than the local history query limit")

        history = self.snapshots.history(market, symbol, interval, limit)
        ordered_snapshots = sorted(
            history["snapshots"], key=lambda item: int(item["analyzed_at_ms"])
        )
        train_count = (
            min(len(ordered_snapshots) - 1, max(1, int(len(ordered_snapshots) * 0.7)))
            if len(ordered_snapshots) >= 2 else 0
        )
        training_ids = {item["snapshot_id"] for item in ordered_snapshots[:train_count]}
        test_ids = {item["snapshot_id"] for item in ordered_snapshots[train_count:]}
        split_timestamp_ms = (
            int(ordered_snapshots[train_count - 1]["analyzed_at_ms"])
            if train_count else None
        )
        summaries: dict[str, Any] = {}
        for hours in self.HORIZONS_HOURS:
            outcomes = []
            pending = missing_reference = 0
            horizon_ms = hours * 3_600_000
            for snapshot in ordered_snapshots:
                analyzed_at = int(snapshot["analyzed_at_ms"])
                reference = snapshot["reference_price"]
                bias = snapshot["bias"]
                regime_labels = _snapshot_regime_labels(snapshot)
                if reference is None or not math.isfinite(float(reference)) or float(reference) <= 0:
                    missing_reference += 1
                    continue

                target_time = analyzed_at + horizon_ms
                # Include the first candle that can close at or after the target.
                query_end = target_time + candle_step
                candles = self.klines.history(
                    market, symbol, price_interval, analyzed_at + 1,
                    query_end, min(5000, max_required),
                )["candles"]
                future = [
                    candle for candle in candles
                    if int(candle["open_time_ms"]) > analyzed_at
                ]
                endpoint = next(
                    (candle for candle in future if int(candle["close_time_ms"]) >= target_time),
                    None,
                )
                if endpoint is None:
                    pending += 1
                    continue

                window = [
                    candle for candle in future
                    if int(candle["close_time_ms"]) <= int(endpoint["close_time_ms"])
                ]
                if not window:
                    pending += 1
                    continue

                first_expected_open = (analyzed_at // candle_step + 1) * candle_step
                last_open = int(window[-1]["open_time_ms"])
                expected_count = max(1, ((last_open - first_expected_open) // candle_step) + 1)
                coverage_complete = (
                    int(window[0]["open_time_ms"]) == first_expected_open
                    and len(window) == expected_count
                    and all(
                        int(window[i]["open_time_ms"]) - int(window[i - 1]["open_time_ms"]) == candle_step
                        for i in range(1, len(window))
                    )
                )

                reference_price = float(reference)
                outcome_close = float(endpoint["close"])
                highest = max(float(candle["high"]) for candle in window)
                lowest = min(float(candle["low"]) for candle in window)
                market_return = (outcome_close - reference_price) / reference_price * 100.0
                if bias == "BULLISH":
                    directional_return = market_return
                    favorable = (highest - reference_price) / reference_price * 100.0
                    adverse = (reference_price - lowest) / reference_price * 100.0
                elif bias == "BEARISH":
                    directional_return = -market_return
                    favorable = (reference_price - lowest) / reference_price * 100.0
                    adverse = (highest - reference_price) / reference_price * 100.0
                else:
                    directional_return = favorable = adverse = None

                outcomes.append({
                    "snapshot_id": snapshot["snapshot_id"],
                    "analyzed_at_ms": analyzed_at,
                    "bias": bias,
                    **regime_labels,
                    "alignment": snapshot["alignment"],
                    "reference_price": reference_price,
                    "outcome_close": outcome_close,
                    "outcome_close_time_ms": int(endpoint["close_time_ms"]),
                    "target_time_ms": target_time,
                    "actual_elapsed_hours": (int(endpoint["close_time_ms"]) - analyzed_at) / 3_600_000,
                    "market_return_percent": market_return,
                    "directional_return_percent": directional_return,
                    "favorable_excursion_percent": favorable,
                    "adverse_excursion_percent": adverse,
                    "directional_positive": directional_return > 0 if directional_return is not None else None,
                    "future_candle_count": len(window),
                    "expected_future_candle_count": expected_count,
                    "future_candle_coverage_complete": coverage_complete,
                    "future_candle_coverage": "COMPLETE" if coverage_complete else "GAPPED_OR_PARTIAL",
                })

            directional = [row for row in outcomes if row["directional_positive"] is not None]
            # Purge training outcomes whose forward label window reaches the holdout boundary.
            unpurged_training_outcomes = [
                row for row in outcomes if row["snapshot_id"] in training_ids
            ]
            training_outcomes = [
                row for row in unpurged_training_outcomes
                if split_timestamp_ms is not None
                and int(row["outcome_close_time_ms"]) < split_timestamp_ms
            ]
            training_purged_overlap_count = (
                len(unpurged_training_outcomes) - len(training_outcomes)
            )
            test_outcomes = [row for row in outcomes if row["snapshot_id"] in test_ids]
            train_directional = [row for row in training_outcomes if row["directional_positive"] is not None]
            test_directional = [row for row in test_outcomes if row["directional_positive"] is not None]
            # Expanding-window walk-forward evaluation of saved outputs (no model fitting).
            walk_forward_folds = []
            if len(ordered_snapshots) >= 4:
                initial_train_count = max(1, len(ordered_snapshots) // 2)
                remaining = ordered_snapshots[initial_train_count:]
                fold_count = min(3, len(remaining))
                base_size, extra = divmod(len(remaining), fold_count)
                cursor = 0
                for fold_index in range(fold_count):
                    block_size = base_size + (1 if fold_index < extra else 0)
                    test_block = remaining[cursor:cursor + block_size]
                    cursor += block_size
                    prior_test_count = sum(len(fold["test_snapshot_ids"]) for fold in walk_forward_folds)
                    train_block = ordered_snapshots[:initial_train_count + prior_test_count]
                    next_fold_start = (
                        int(remaining[cursor]["analyzed_at_ms"]) if cursor < len(remaining) else None
                    )
                    block_ids = {item["snapshot_id"] for item in test_block}
                    fold_rows = [
                        row for row in outcomes
                        if row["snapshot_id"] in block_ids
                        and (next_fold_start is None or row["outcome_close_time_ms"] < next_fold_start)
                    ]
                    fold_directional = [row for row in fold_rows if row["directional_positive"] is not None]
                    directional_stats = _directional_statistics(fold_directional)
                    fold_non_overlapping = _non_overlapping_rows(fold_directional)
                    fold_non_overlapping_stats = _directional_statistics(fold_non_overlapping)
                    positives = directional_stats["positive_count"]
                    walk_forward_folds.append({
                        "fold": fold_index + 1,
                        "training_snapshot_count": len(train_block),
                        "test_snapshot_count": len(test_block),
                        "test_start_ms": int(test_block[0]["analyzed_at_ms"]),
                        "test_end_ms": int(test_block[-1]["analyzed_at_ms"]),
                        "outcome_cutoff_exclusive_ms": next_fold_start,
                        "test_snapshot_ids": [item["snapshot_id"] for item in test_block],
                        "test_matured_outcome_count": len(fold_rows),
                        "test_directional_sample_size": len(fold_directional),
                        "test_positive_count": positives,
                        "test_negative_count": len(fold_directional) - positives,
                        "test_directional_positive_fraction": directional_stats["positive_fraction"],
                        "test_directional_positive_fraction_ci_95_wilson": directional_stats["positive_fraction_ci_95_wilson"],
                        "minimum_directional_sample_size": directional_stats["minimum_sample_size"],
                        "sample_size_status": directional_stats["sample_size_status"],
                        "non_overlapping_directional_sample_size": len(fold_non_overlapping),
                        "non_overlapping_positive_fraction": fold_non_overlapping_stats["positive_fraction"],
                        "non_overlapping_positive_fraction_ci_95_wilson": fold_non_overlapping_stats["positive_fraction_ci_95_wilson"],
                        "overlap_excluded_count": len(fold_directional) - len(fold_non_overlapping),
                        "test_mean_directional_return_percent": (
                            sum(row["directional_return_percent"] for row in fold_directional) / len(fold_directional)
                            if fold_directional else None
                        ),
                        "test_coverage_complete_count": sum(row["future_candle_coverage_complete"] for row in fold_rows),
                    })
            walk_forward_rows = [
                row for fold in walk_forward_folds for row in outcomes
                if row["snapshot_id"] in set(fold["test_snapshot_ids"])
                and (fold["outcome_cutoff_exclusive_ms"] is None
                     or row["outcome_close_time_ms"] < fold["outcome_cutoff_exclusive_ms"])
            ]
            walk_forward_directional = [row for row in walk_forward_rows if row["directional_positive"] is not None]
            walk_forward_stats = _directional_statistics(walk_forward_directional)
            walk_forward_non_overlapping = _non_overlapping_rows(walk_forward_directional)
            walk_forward_non_overlapping_stats = _directional_statistics(walk_forward_non_overlapping)
            walk_forward_positive = walk_forward_stats["positive_count"]
            walk_forward_consistency = _walk_forward_consistency(walk_forward_folds)
            walk_forward = {
                "method": "Expanding-window walk-forward evaluation of saved confluence outputs. Each fold trains only on earlier snapshot history; no model fitting or tuning is performed. Outcomes crossing the next test-fold boundary are excluded.",
                "status": (
                    "INSUFFICIENT_SNAPSHOTS" if len(ordered_snapshots) < 4
                    else "COMPLETED" if walk_forward_rows else "INSUFFICIENT_MATURED_TEST_OUTCOMES"
                ),
                "initial_training_snapshot_count": max(1, len(ordered_snapshots) // 2) if len(ordered_snapshots) >= 4 else 0,
                "fold_count": len(walk_forward_folds),
                "test_snapshot_count": sum(fold["test_snapshot_count"] for fold in walk_forward_folds),
                "test_matured_outcome_count": len(walk_forward_rows),
                "test_directional_sample_size": len(walk_forward_directional),
                "test_positive_count": walk_forward_positive,
                "test_negative_count": len(walk_forward_directional) - walk_forward_positive,
                "test_directional_positive_fraction": walk_forward_stats["positive_fraction"],
                "test_directional_positive_fraction_ci_95_wilson": walk_forward_stats["positive_fraction_ci_95_wilson"],
                "minimum_directional_sample_size": walk_forward_stats["minimum_sample_size"],
                "sample_size_status": walk_forward_stats["sample_size_status"],
                "non_overlapping_directional_sample_size": len(walk_forward_non_overlapping),
                "non_overlapping_positive_count": walk_forward_non_overlapping_stats["positive_count"],
                "non_overlapping_positive_fraction": walk_forward_non_overlapping_stats["positive_fraction"],
                "non_overlapping_positive_fraction_ci_95_wilson": walk_forward_non_overlapping_stats["positive_fraction_ci_95_wilson"],
                "overlap_excluded_count": len(walk_forward_directional) - len(walk_forward_non_overlapping),
                "test_mean_directional_return_percent": (
                    sum(row["directional_return_percent"] for row in walk_forward_directional)
                    / len(walk_forward_directional) if walk_forward_directional else None
                ),
                "test_coverage_complete_count": sum(row["future_candle_coverage_complete"] for row in walk_forward_rows),
                "consistency_assessment": walk_forward_consistency,
                "folds": walk_forward_folds,
            }
            test_directional_stats = _directional_statistics(test_directional)
            holdout_non_overlapping = _non_overlapping_rows(test_directional)
            holdout_non_overlapping_stats = _directional_statistics(holdout_non_overlapping)
            out_of_sample = {
                "method": "Chronological holdout: earliest 70% of saved snapshots are the training period; latest 30% are the untouched test period. Training outcomes whose forward label windows reach or cross the split timestamp are purged to prevent boundary leakage. No fitting or tuning is performed by this evaluator.",
                "status": (
                    "INSUFFICIENT_SNAPSHOTS" if len(ordered_snapshots) < 2
                    else "COMPLETED" if test_outcomes else "INSUFFICIENT_TEST_OUTCOMES"
                ),
                "split_fraction": 0.7,
                "split_timestamp_ms": split_timestamp_ms,
                "training_snapshot_count": len(training_ids),
                "test_snapshot_count": len(test_ids),
                "training_matured_outcome_count": len(training_outcomes),
                "training_purged_overlap_count": training_purged_overlap_count,
                "test_matured_outcome_count": len(test_outcomes),
                "test_regime_stability": _out_of_sample_regime_stability(test_outcomes),
                "regime_transition_degradation": _regime_transition_degradation(test_outcomes),
                "regime_transition_analysis": _regime_transition_analysis(test_outcomes),
                "training_directional_sample_size": len(train_directional),
                "test_directional_sample_size": len(test_directional),
                "test_positive_count": test_directional_stats["positive_count"],
                "test_negative_count": test_directional_stats["negative_count"],
                "test_directional_positive_fraction": test_directional_stats["positive_fraction"] if len(ordered_snapshots) >= 2 else None,
                "test_directional_positive_fraction_ci_95_wilson": test_directional_stats["positive_fraction_ci_95_wilson"] if len(ordered_snapshots) >= 2 else None,
                "minimum_directional_sample_size": test_directional_stats["minimum_sample_size"],
                "sample_size_status": test_directional_stats["sample_size_status"],
                "non_overlapping_directional_sample_size": len(holdout_non_overlapping),
                "non_overlapping_positive_count": holdout_non_overlapping_stats["positive_count"],
                "non_overlapping_positive_fraction": holdout_non_overlapping_stats["positive_fraction"],
                "non_overlapping_positive_fraction_ci_95_wilson": holdout_non_overlapping_stats["positive_fraction_ci_95_wilson"],
                "overlap_excluded_count": len(test_directional) - len(holdout_non_overlapping),
                "test_mean_directional_return_percent": (
                    sum(row["directional_return_percent"] for row in test_directional) / len(test_directional)
                    if test_directional else None
                ),
                "test_coverage_complete_count": sum(
                    row["future_candle_coverage_complete"] for row in test_outcomes
                ),
                "test_outcomes": test_outcomes,
            }
            non_overlapping_directional = _non_overlapping_rows(directional)
            non_overlapping_stats = _directional_statistics(non_overlapping_directional)
            dependence_adjusted = {
                "method": "Maximum-cardinality interval scheduling over each outcome window [analyzed_at_ms, outcome_close_time_ms]. Only non-overlapping directional outcome windows are retained; this reduces repeated exposure but does not remove all serial dependence.",
                "directional_sample_size": len(non_overlapping_directional),
                "positive_count": non_overlapping_stats["positive_count"],
                "negative_count": non_overlapping_stats["negative_count"],
                "positive_fraction": non_overlapping_stats["positive_fraction"],
                "positive_fraction_ci_95_wilson": non_overlapping_stats["positive_fraction_ci_95_wilson"],
                "overlap_excluded_count": len(directional) - len(non_overlapping_directional),
            }
            bias_breakdown = {}
            for bias_name in ("BULLISH", "BEARISH", "MIXED", "UNKNOWN"):
                bias_rows = [row for row in outcomes if row["bias"] == bias_name]
                bias_directional = [
                    row for row in bias_rows if row["directional_positive"] is not None
                ]
                bias_breakdown[bias_name] = {
                    "sample_size": len(bias_rows),
                    "directional_sample_size": len(bias_directional),
                    "positive_count": sum(row["directional_positive"] for row in bias_directional),
                    "negative_count": sum(not row["directional_positive"] for row in bias_directional),
                    "positive_fraction": (
                        sum(row["directional_positive"] for row in bias_directional) / len(bias_directional)
                        if bias_directional else None
                    ),
                    "mean_directional_return_percent": (
                        sum(row["directional_return_percent"] for row in bias_directional) / len(bias_directional)
                        if bias_directional else None
                    ),
                    "coverage_complete_count": sum(
                        row["future_candle_coverage_complete"] for row in bias_rows
                    ),
                }
            regime_breakdown = {}
            for dimension in ("market_regime", "volatility_regime", "structure_regime"):
                grouped = {}
                for row in outcomes:
                    grouped.setdefault(row[dimension], []).append(row)
                regime_breakdown[dimension] = {}
                for label, group_rows in sorted(grouped.items()):
                    group_directional = [row for row in group_rows if row["directional_positive"] is not None]
                    positive_count = sum(row["directional_positive"] for row in group_directional)
                    regime_breakdown[dimension][label] = {
                        "sample_size": len(group_rows),
                        "directional_sample_size": len(group_directional),
                        "positive_count": positive_count,
                        "negative_count": len(group_directional) - positive_count,
                        "positive_fraction": positive_count / len(group_directional) if group_directional else None,
                        "mean_directional_return_percent": (
                            sum(row["directional_return_percent"] for row in group_directional) / len(group_directional)
                            if group_directional else None
                        ),
                        "coverage_complete_count": sum(row["future_candle_coverage_complete"] for row in group_rows),
                    }
            regime_bias_breakdown = {}
            for dimension in ("market_regime", "volatility_regime", "structure_regime"):
                dimension_groups = {}
                for row in outcomes:
                    dimension_groups.setdefault(row[dimension], []).append(row)
                regime_bias_breakdown[dimension] = {}
                for regime_label, regime_rows in sorted(dimension_groups.items()):
                    regime_bias_breakdown[dimension][regime_label] = {}
                    for bias_name in ("BULLISH", "BEARISH", "MIXED", "UNKNOWN"):
                        group = [row for row in regime_rows if row["bias"] == bias_name]
                        directional_group = [row for row in group if row["directional_positive"] is not None]
                        directional_stats = _directional_statistics(directional_group)
                        positives = directional_stats["positive_count"]
                        non_overlapping_group = _non_overlapping_rows(directional_group)
                        non_overlapping_stats = _directional_statistics(non_overlapping_group)
                        regime_bias_breakdown[dimension][regime_label][bias_name] = {
                            "sample_size": len(group),
                            "directional_sample_size": len(directional_group),
                            "positive_count": positives,
                            "negative_count": len(directional_group) - positives,
                            "positive_fraction": directional_stats["positive_fraction"],
                            "positive_fraction_ci_95_wilson": directional_stats["positive_fraction_ci_95_wilson"],
                            "minimum_directional_sample_size": directional_stats["minimum_sample_size"],
                            "sample_size_status": directional_stats["sample_size_status"],
                            "non_overlapping_directional_sample_size": len(non_overlapping_group),
                            "non_overlapping_positive_count": non_overlapping_stats["positive_count"],
                            "non_overlapping_positive_fraction": non_overlapping_stats["positive_fraction"],
                            "non_overlapping_positive_fraction_ci_95_wilson": non_overlapping_stats["positive_fraction_ci_95_wilson"],
                            "overlap_excluded_count": len(directional_group) - len(non_overlapping_group),
                            "mean_directional_return_percent": (
                                sum(row["directional_return_percent"] for row in directional_group) / len(directional_group)
                                if directional_group else None
                            ),
                            "coverage_complete_count": sum(row["future_candle_coverage_complete"] for row in group),
                        }
            regime_bias_alignment_breakdown = {}
            for dimension in ("market_regime", "volatility_regime", "structure_regime"):
                dimension_groups = {}
                for row in outcomes:
                    dimension_groups.setdefault(row[dimension], []).append(row)
                regime_bias_alignment_breakdown[dimension] = {}
                for regime_label, regime_rows in sorted(dimension_groups.items()):
                    regime_bias_alignment_breakdown[dimension][regime_label] = {}
                    for bias_name in ("BULLISH", "BEARISH", "MIXED", "UNKNOWN"):
                        bias_rows = [row for row in regime_rows if row["bias"] == bias_name]
                        alignment_groups = {}
                        for row in bias_rows:
                            alignment = str(row.get("alignment") or "UNCLASSIFIED")
                            alignment_groups.setdefault(alignment, []).append(row)
                        regime_bias_alignment_breakdown[dimension][regime_label][bias_name] = {}
                        for alignment, group in sorted(alignment_groups.items()):
                            directional_group = [
                                row for row in group if row["directional_positive"] is not None
                            ]
                            directional_stats = _directional_statistics(directional_group)
                            non_overlapping_group = _non_overlapping_rows(directional_group)
                            non_overlapping_stats = _directional_statistics(non_overlapping_group)
                            regime_bias_alignment_breakdown[dimension][regime_label][bias_name][alignment] = {
                                "sample_size": len(group),
                                "directional_sample_size": len(directional_group),
                                "positive_count": directional_stats["positive_count"],
                                "negative_count": directional_stats["negative_count"],
                                "positive_fraction": directional_stats["positive_fraction"],
                                "positive_fraction_ci_95_wilson": directional_stats["positive_fraction_ci_95_wilson"],
                                "minimum_directional_sample_size": directional_stats["minimum_sample_size"],
                                "sample_size_status": directional_stats["sample_size_status"],
                                "non_overlapping_directional_sample_size": len(non_overlapping_group),
                                "non_overlapping_positive_count": non_overlapping_stats["positive_count"],
                                "non_overlapping_positive_fraction": non_overlapping_stats["positive_fraction"],
                                "non_overlapping_positive_fraction_ci_95_wilson": non_overlapping_stats["positive_fraction_ci_95_wilson"],
                                "overlap_excluded_count": len(directional_group) - len(non_overlapping_group),
                                "mean_directional_return_percent": (
                                    sum(row["directional_return_percent"] for row in directional_group) / len(directional_group)
                                    if directional_group else None
                                ),
                                "coverage_complete_count": sum(
                                    row["future_candle_coverage_complete"] for row in group
                                ),
                            }
            signal_quality = _signal_quality_assessment(outcomes)
            signal_quality_by_regime = {}
            for dimension in ("market_regime", "volatility_regime", "structure_regime"):
                groups: dict[str, list[dict[str, Any]]] = {}
                for row in outcomes:
                    groups.setdefault(row[dimension], []).append(row)
                signal_quality_by_regime[dimension] = {
                    label: _signal_quality_assessment(group_rows)
                    for label, group_rows in sorted(groups.items())
                }
            summaries[str(hours)] = {
                "label": self.HORIZON_LABELS[hours],
                "signal_quality": signal_quality,
                "signal_quality_by_regime": signal_quality_by_regime,
                "horizon_hours": hours,
                "horizon_days": hours / 24,
                "status": "COMPLETED" if outcomes else "INSUFFICIENT_FUTURE_DATA",
                "sample_size": len(outcomes),
                "directional_sample_size": len(directional),
                "bias_breakdown": bias_breakdown,
                "regime_breakdown": regime_breakdown,
                "regime_bias_breakdown": regime_bias_breakdown,
                "regime_bias_alignment_breakdown": regime_bias_alignment_breakdown,
                "out_of_sample": out_of_sample,
                "walk_forward": walk_forward,
                "dependence_adjusted": dependence_adjusted,
                "pending_or_not_matured": pending,
                "missing_reference_price": missing_reference,
                "coverage_complete_count": sum(row["future_candle_coverage_complete"] for row in outcomes),
                "coverage_partial_count": sum(not row["future_candle_coverage_complete"] for row in outcomes),
                "directional_positive_fraction": (
                    sum(row["directional_positive"] for row in directional) / len(directional)
                    if directional else None
                ),
                "directional_positive_fraction_ci_95_wilson": (
                    _directional_statistics(directional)["positive_fraction_ci_95_wilson"]
                ),
                "mean_directional_return_percent": (
                    sum(row["directional_return_percent"] for row in directional) / len(directional)
                    if directional else None
                ),
                "mean_favorable_excursion_percent": (
                    sum(row["favorable_excursion_percent"] for row in directional) / len(directional)
                    if directional else None
                ),
                "mean_adverse_excursion_percent": (
                    sum(row["adverse_excursion_percent"] for row in directional) / len(directional)
                    if directional else None
                ),
                "outcomes": outcomes,
            }
            summaries[str(hours)]["historical_vs_walk_forward"] = _historical_walk_forward_comparison(
                summaries[str(hours)], walk_forward,
            )
            summaries[str(hours)]["data_quality_risk_assessment"] = _data_quality_risk_assessment(
                summaries[str(hours)],
            )


        minimum_ranking_sample_size = 30
        ranking_definitions = {
            "directional_positive_fraction": {
                "label": "Directional positive fraction",
                "sample_field": "directional_sample_size",
                "ci_field": "positive_fraction_ci_95_wilson",
            },
            "mean_directional_return_percent": {
                "label": "Mean directional return",
                "sample_field": "directional_sample_size",
                "ci_field": None,
            },
            "non_overlapping_positive_fraction": {
                "label": "Non-overlapping positive fraction",
                "sample_field": "dependence_adjusted.directional_sample_size",
                "ci_field": "dependence_adjusted.positive_fraction_ci_95_wilson",
            },
        }
        horizon_rankings = {}
        for metric, definition in ranking_definitions.items():
            eligible = []
            excluded = []
            for horizon_key, horizon_data in summaries.items():
                sample_field = definition["sample_field"]
                if "." in sample_field:
                    parent, child = sample_field.split(".", 1)
                    sample_size = (horizon_data.get(parent) or {}).get(child, 0)
                else:
                    sample_size = horizon_data.get(sample_field, 0)
                if metric == "non_overlapping_positive_fraction":
                    value = (horizon_data.get("dependence_adjusted") or {}).get("positive_fraction")
                    ci = (horizon_data.get("dependence_adjusted") or {}).get("positive_fraction_ci_95_wilson")
                else:
                    value = horizon_data.get(metric)
                    ci_field = definition["ci_field"]
                    ci = horizon_data.get(ci_field) if ci_field else None
                if sample_size < minimum_ranking_sample_size:
                    excluded.append({
                        "horizon": horizon_data["label"],
                        "horizon_hours": horizon_data["horizon_hours"],
                        "sample_size": sample_size,
                        "reason": "BELOW_MINIMUM_SAMPLE_SIZE",
                    })
                elif value is None or not math.isfinite(float(value)):
                    excluded.append({
                        "horizon": horizon_data["label"],
                        "horizon_hours": horizon_data["horizon_hours"],
                        "sample_size": sample_size,
                        "reason": "METRIC_UNAVAILABLE",
                    })
                else:
                    eligible.append({
                        "horizon": horizon_data["label"],
                        "horizon_hours": horizon_data["horizon_hours"],
                        "sample_size": sample_size,
                        "value": value,
                        "confidence_interval_95_wilson": ci,
                    })
            eligible.sort(key=lambda row: (-row["value"], row["horizon_hours"]))
            ranked = []
            previous_value = None
            current_rank = 0
            for index, row in enumerate(eligible, start=1):
                if previous_value is None or row["value"] != previous_value:
                    current_rank = index
                ranked.append({"rank": current_rank, **row})
                previous_value = row["value"]
            horizon_rankings[metric] = {
                "label": definition["label"],
                "higher_is_better": True,
                "minimum_sample_size": minimum_ranking_sample_size,
                "ranked": ranked,
                "excluded": excluded,
            }

        historical_leaderboard = {
            "status": "DESCRIPTIVE_ONLY",
            "minimum_sample_size": minimum_ranking_sample_size,
            "dimensions": {},
            "method": "Within each horizon and regime dimension, groups are ranked separately by directional positive fraction, mean directional return, and non-overlapping positive fraction. Groups below the metric-specific sample threshold are excluded. This is a historical descriptive comparison, not a forecast or profitability claim.",
        }
        dimension_titles = {
            "market_regime": "Market regime",
            "volatility_regime": "Volatility regime",
            "structure_regime": "Structure regime",
        }
        for dimension, dimension_title in dimension_titles.items():
            historical_leaderboard["dimensions"][dimension] = {}
            for horizon_key, horizon_data in summaries.items():
                breakdown = (horizon_data.get("regime_bias_alignment_breakdown") or {}).get(dimension) or {}
                records = []
                for regime_label, biases in breakdown.items():
                    for bias_name, alignments in biases.items():
                        for alignment_label, stats in alignments.items():
                            records.append({
                                "regime": regime_label,
                                "bias": bias_name,
                                "alignment": alignment_label,
                                "sample_size": stats["sample_size"],
                                "directional_sample_size": stats["directional_sample_size"],
                                "positive_fraction": stats["positive_fraction"],
                                "positive_fraction_ci_95_wilson": stats["positive_fraction_ci_95_wilson"],
                                "mean_directional_return_percent": stats["mean_directional_return_percent"],
                                "non_overlapping_directional_sample_size": stats["non_overlapping_directional_sample_size"],
                                "non_overlapping_positive_fraction": stats["non_overlapping_positive_fraction"],
                                "non_overlapping_positive_fraction_ci_95_wilson": stats["non_overlapping_positive_fraction_ci_95_wilson"],
                                "overlap_excluded_count": stats["overlap_excluded_count"],
                                "sample_size_status": stats["sample_size_status"],
                                "coverage_complete_count": stats["coverage_complete_count"],
                            })
                            records[-1]["reliability_assessment"] = _reliability_assessment(records[-1])
                metric_definitions = (
                    ("positive_fraction", "Directional positive fraction", "directional_sample_size", "positive_fraction_ci_95_wilson"),
                    ("mean_directional_return_percent", "Mean directional return", "directional_sample_size", None),
                    ("non_overlapping_positive_fraction", "Non-overlapping positive fraction", "non_overlapping_directional_sample_size", "non_overlapping_positive_fraction_ci_95_wilson"),
                )
                metric_rankings = {}
                for metric, label, sample_field, ci_field in metric_definitions:
                    eligible = []
                    excluded = []
                    for record in records:
                        sample_size = record[sample_field]
                        value = record[metric]
                        identity = {
                            "regime": record["regime"],
                            "bias": record["bias"],
                            "alignment": record["alignment"],
                            "sample_size": sample_size,
                        }
                        if sample_size < minimum_ranking_sample_size:
                            excluded.append({**identity, "reason": "BELOW_MINIMUM_SAMPLE_SIZE"})
                        elif value is None or not math.isfinite(float(value)):
                            excluded.append({**identity, "reason": "METRIC_UNAVAILABLE"})
                        else:
                            eligible.append({
                                **identity,
                                "value": value,
                                "confidence_interval_95_wilson": record[ci_field] if ci_field else None,
                                "directional_sample_size": record["directional_sample_size"],
                                "non_overlapping_directional_sample_size": record["non_overlapping_directional_sample_size"],
                                "mean_directional_return_percent": record["mean_directional_return_percent"],
                                "positive_fraction": record["positive_fraction"],
                                "non_overlapping_positive_fraction": record["non_overlapping_positive_fraction"],
                                "overlap_excluded_count": record["overlap_excluded_count"],
                                "reliability_assessment": record["reliability_assessment"],
                            })
                    eligible.sort(key=lambda row: (-row["value"], row["regime"], row["bias"], row["alignment"]))
                    ranked = []
                    previous_value = None
                    current_rank = 0
                    for index, row in enumerate(eligible, start=1):
                        if previous_value is None or row["value"] != previous_value:
                            current_rank = index
                        ranked.append({"rank": current_rank, **row})
                        previous_value = row["value"]
                    metric_rankings[metric] = {
                        "label": label,
                        "minimum_sample_size": minimum_ranking_sample_size,
                        "ranked": ranked,
                        "excluded": excluded,
                    }
                historical_leaderboard["dimensions"][dimension][horizon_key] = {
                    "horizon": horizon_data["label"],
                    "horizon_hours": horizon_data["horizon_hours"],
                    "rankings": metric_rankings,
                    "reliability_summary": {
                        "group_count": len(records),
                        "insufficient_evidence_group_count": sum(
                            row["reliability_assessment"]["classification"] == "INSUFFICIENT_EVIDENCE"
                            for row in records
                        ),
                        "interval_includes_50_percent_group_count": sum(
                            row["reliability_assessment"]["classification"] == "INTERVAL_INCLUDES_50_PERCENT"
                            for row in records
                        ),
                        "interval_above_50_percent_group_count": sum(
                            row["reliability_assessment"]["classification"] == "INTERVAL_ABOVE_50_PERCENT"
                            for row in records
                        ),
                        "interval_below_50_percent_group_count": sum(
                            row["reliability_assessment"]["classification"] == "INTERVAL_BELOW_50_PERCENT"
                            for row in records
                        ),
                    },
                }

        return {
            "status": "COMPLETED" if history["snapshots"] else "NO_STORED_SNAPSHOTS",
            "market": market.upper(),
            "symbol": symbol.upper(),
            "interval": interval,
            "price_interval": price_interval,
            "snapshot_count": history["returned_count"],
            "horizon_count": len(self.HORIZONS_HOURS),
            "horizons": summaries,
            "historical_leaderboard": historical_leaderboard,
            "horizon_comparison": {
                "status": "DESCRIPTIVE_ONLY",
                "minimum_sample_size": minimum_ranking_sample_size,
                "rankings": horizon_rankings,
                "method": "Separate metric rankings only; no composite score. Horizons below the minimum sample size or without a metric are excluded, not assigned a rank. Rankings do not establish predictive validity or profitability.",
            },
            "method": {
                "baseline": "Saved close of the last local candle fully closed at or before snapshot time.",
                "future_data": "Only candles whose open_time_ms is strictly later than analyzed_at_ms are eligible.",
                "hourly_comparison": "Default price_interval is 1h; select 15m or 30m for finer resolution.",
                "one_month": "30 fixed days (720 hours), not a calendar-month calculation.",
                "directional_metric": "Directional-positive fraction is descriptive, not a validated strategy hit rate.",
                "mixed_unknown": "Retained in raw outcomes but excluded from directional aggregates.",
                "regime_stratification": "Groups outcomes by saved market, volatility and structure regime labels; missing labels are UNCLASSIFIED. Groups are descriptive and may have small samples.",
                "out_of_sample": "Chronological 70/30 holdout by snapshot analysis time. This is a temporal evaluation split, not a trained or tuned predictive model.",
                "walk_forward": "Expanding-window temporal folds evaluate saved confluence outputs; no predictive model is trained or tuned. Outcomes crossing the next test fold boundary are excluded.",
                "confidence_interval": "Nominal 95% Wilson score interval for the directional-positive fraction. The 30-sample threshold is a reporting flag, not a universal adequacy guarantee. The interval assumes independent Bernoulli observations and does not adjust for serial dependence or overlapping market horizons.",
                "overlap_control": "A separate dependence_adjusted result uses maximum-cardinality interval scheduling to retain only non-overlapping [snapshot time, outcome close time] windows. This reduces direct outcome-window overlap but cannot eliminate broader serial dependence, regime clustering, or dependence between market observations.",
                "mfe_mae": "Directional high/low excursion; not a stop/target simulation.",
                "coverage": "Every outcome reports whether the local candle sequence is continuous from the first expected candle through its endpoint.",
            },
            "limitations": [
                "Local history only; missing candles are not interpolated or backfilled.",
                "A horizon is evaluated only when a stored candle closes at or after its target time.",
                "No execution, fees, slippage, funding, leverage, position sizing, stop or target is simulated.",
                "Not strategy profitability, investment advice, or a forecast.",
                "The out-of-sample section is a chronological holdout summary only; it does not train, tune, or validate a predictive model.",
            ],
        }



    def price_path(
        self, market: str, symbol: str, snapshot_id: str,
        price_interval: str = "1h", hours: int = 720,
    ) -> dict[str, Any]:
        """Return one bounded local OHLC path for a saved snapshot."""
        if price_interval not in self.INTERVAL_MS:
            raise ValueError("Unsupported price_interval")
        if not 1 <= hours <= 720:
            raise ValueError("hours must be between 1 and 720")
        snapshot = self.snapshots.get_snapshot(market, symbol, snapshot_id)
        if snapshot is None:
            raise ValueError("Snapshot not found for the requested market and symbol")
        analyzed_at = int(snapshot["analyzed_at_ms"])
        reference = snapshot["reference_price"]
        if reference is None or not math.isfinite(float(reference)) or float(reference) <= 0:
            raise ValueError("Snapshot has no valid reference price")
        step = self.INTERVAL_MS[price_interval]
        target_time = analyzed_at + hours * 3_600_000
        query_limit = min(5000, (hours * 3_600_000) // step + 3)
        candles = self.klines.history(
            market, symbol, price_interval, analyzed_at + 1,
            target_time + step, query_limit,
        )["candles"]
        eligible_all = sorted(
            (c for c in candles if int(c["open_time_ms"]) > analyzed_at),
            key=lambda c: int(c["open_time_ms"]),
        )
        endpoint = next(
            (c for c in eligible_all if int(c["close_time_ms"]) >= target_time),
            None,
        )
        eligible = (
            [c for c in eligible_all if int(c["open_time_ms"]) <= int(endpoint["open_time_ms"])]
            if endpoint is not None else eligible_all
        )
        if not eligible:
            return {
                "status": "PENDING_NO_FUTURE_CANDLES", "snapshot_id": snapshot_id,
                "market": market.upper(), "symbol": symbol.upper(),
                "price_interval": price_interval, "hours": hours,
                "reference_price": float(reference), "candles": [],
                "coverage": {"complete": False, "expected_count": 0, "received_count": 0},
            }
        reference_price = float(reference)
        first_expected = (analyzed_at // step + 1) * step
        last_open = int(eligible[-1]["open_time_ms"])
        expected_count = max(1, ((last_open - first_expected) // step) + 1)
        complete = (
            int(eligible[0]["open_time_ms"]) == first_expected
            and len(eligible) == expected_count
            and all(
                int(eligible[i]["open_time_ms"]) - int(eligible[i - 1]["open_time_ms"]) == step
                for i in range(1, len(eligible))
            )
        )
        path = [{
            "open_time_ms": int(c["open_time_ms"]),
            "close_time_ms": int(c["close_time_ms"]),
            "open": float(c["open"]), "high": float(c["high"]),
            "low": float(c["low"]), "close": float(c["close"]),
            "change_from_reference_percent": (float(c["close"]) - reference_price) / reference_price * 100.0,
        } for c in eligible]
        actual_change = path[-1]["change_from_reference_percent"]
        bias = snapshot["bias"]
        bias_aligned_change = (
            actual_change if bias == "BULLISH" else
            -actual_change if bias == "BEARISH" else None
        )
        bias_vs_actual = (
            "ALIGNED" if bias_aligned_change is not None and bias_aligned_change > 0 else
            "OPPOSED" if bias_aligned_change is not None and bias_aligned_change < 0 else
            "FLAT_OR_UNCLEAR" if bias_aligned_change is not None else "NON_DIRECTIONAL_BIAS"
        )
        return {
            "status": "COMPLETED" if endpoint is not None else "PENDING_HORIZON_NOT_MATURED", "snapshot_id": snapshot_id,
            "market": market.upper(), "symbol": symbol.upper(),
            "analyzed_at_ms": analyzed_at, "bias": snapshot["bias"],
            "alignment": snapshot["alignment"], "price_interval": price_interval,
            "hours": hours, "reference_price": reference_price,
            "actual_market_change_percent": actual_change,
            "bias_aligned_change_percent": bias_aligned_change,
            "bias_vs_actual": bias_vs_actual,
            "reference_close_time_ms": snapshot.get("reference_close_time_ms"),
            "target_time_ms": target_time, "target_reached": endpoint is not None, "candles": path,
            "coverage": {
                "complete": complete, "expected_count": expected_count,
                "received_count": len(path),
                "status": "COMPLETE" if complete else "GAPPED_OR_PARTIAL",
            },
            "method": "Local stored OHLC candles only; no interpolation or backfill.",
        }
