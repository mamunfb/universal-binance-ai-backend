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
            for snapshot in history["snapshots"]:
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
            training_outcomes = [row for row in outcomes if row["snapshot_id"] in training_ids]
            test_outcomes = [row for row in outcomes if row["snapshot_id"] in test_ids]
            train_directional = [row for row in training_outcomes if row["directional_positive"] is not None]
            test_directional = [row for row in test_outcomes if row["directional_positive"] is not None]
            out_of_sample = {
                "method": "Chronological holdout: earliest 70% of saved snapshots are the training period; latest 30% are the test period. No fitting or tuning is performed by this evaluator.",
                "status": (
                    "INSUFFICIENT_SNAPSHOTS" if len(ordered_snapshots) < 2
                    else "COMPLETED" if test_outcomes else "INSUFFICIENT_TEST_OUTCOMES"
                ),
                "split_fraction": 0.7,
                "split_timestamp_ms": split_timestamp_ms,
                "training_snapshot_count": len(training_ids),
                "test_snapshot_count": len(test_ids),
                "training_matured_outcome_count": len(training_outcomes),
                "test_matured_outcome_count": len(test_outcomes),
                "training_directional_sample_size": len(train_directional),
                "test_directional_sample_size": len(test_directional),
                "test_positive_count": sum(row["directional_positive"] for row in test_directional),
                "test_negative_count": sum(not row["directional_positive"] for row in test_directional),
                "test_directional_positive_fraction": (
                    sum(row["directional_positive"] for row in test_directional) / len(test_directional)
                    if test_directional else None
                ),
                "test_mean_directional_return_percent": (
                    sum(row["directional_return_percent"] for row in test_directional) / len(test_directional)
                    if test_directional else None
                ),
                "test_coverage_complete_count": sum(
                    row["future_candle_coverage_complete"] for row in test_outcomes
                ),
                "test_outcomes": test_outcomes,
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
                        positives = sum(row["directional_positive"] for row in directional_group)
                        regime_bias_breakdown[dimension][regime_label][bias_name] = {
                            "sample_size": len(group),
                            "directional_sample_size": len(directional_group),
                            "positive_count": positives,
                            "negative_count": len(directional_group) - positives,
                            "positive_fraction": positives / len(directional_group) if directional_group else None,
                            "mean_directional_return_percent": (
                                sum(row["directional_return_percent"] for row in directional_group) / len(directional_group)
                                if directional_group else None
                            ),
                            "coverage_complete_count": sum(row["future_candle_coverage_complete"] for row in group),
                        }
            summaries[str(hours)] = {
                "label": self.HORIZON_LABELS[hours],
                "horizon_hours": hours,
                "horizon_days": hours / 24,
                "status": "COMPLETED" if outcomes else "INSUFFICIENT_FUTURE_DATA",
                "sample_size": len(outcomes),
                "directional_sample_size": len(directional),
                "bias_breakdown": bias_breakdown,
                "regime_breakdown": regime_breakdown,
                "regime_bias_breakdown": regime_bias_breakdown,
                "out_of_sample": out_of_sample,
                "pending_or_not_matured": pending,
                "missing_reference_price": missing_reference,
                "coverage_complete_count": sum(row["future_candle_coverage_complete"] for row in outcomes),
                "coverage_partial_count": sum(not row["future_candle_coverage_complete"] for row in outcomes),
                "directional_positive_fraction": (
                    sum(row["directional_positive"] for row in directional) / len(directional)
                    if directional else None
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


        return {
            "status": "COMPLETED" if history["snapshots"] else "NO_STORED_SNAPSHOTS",
            "market": market.upper(),
            "symbol": symbol.upper(),
            "interval": interval,
            "price_interval": price_interval,
            "snapshot_count": history["returned_count"],
            "horizon_count": len(self.HORIZONS_HOURS),
            "horizons": summaries,
            "method": {
                "baseline": "Saved close of the last local candle fully closed at or before snapshot time.",
                "future_data": "Only candles whose open_time_ms is strictly later than analyzed_at_ms are eligible.",
                "hourly_comparison": "Default price_interval is 1h; select 15m or 30m for finer resolution.",
                "one_month": "30 fixed days (720 hours), not a calendar-month calculation.",
                "directional_metric": "Directional-positive fraction is descriptive, not a validated strategy hit rate.",
                "mixed_unknown": "Retained in raw outcomes but excluded from directional aggregates.",
                "regime_stratification": "Groups outcomes by saved market, volatility and structure regime labels; missing labels are UNCLASSIFIED. Groups are descriptive and may have small samples.",
                "out_of_sample": "Chronological 70/30 holdout by snapshot analysis time. This is a temporal evaluation split, not a trained or tuned predictive model.",
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
