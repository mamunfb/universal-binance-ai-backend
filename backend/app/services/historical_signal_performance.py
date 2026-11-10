from __future__ import annotations

import math
from statistics import median
from typing import Any

from app.services.advanced_derivatives_analysis import DerivativesSignalStore
from app.services.historical_klines import HistoricalKlineStore


def _explicit_signal_direction(analysis: dict[str, Any]) -> str | None:
    """Read only an explicit directional hypothesis; never infer one from descriptive OI labels."""
    candidate = analysis.get("signal_direction")
    if candidate is None:
        candidate = (analysis.get("directional_signal") or {}).get("direction")
    if candidate is None:
        candidate = (analysis.get("confluence") or {}).get("bias")
    normalized = str(candidate or "").strip().upper()
    if normalized in {"BULLISH", "BUY", "LONG", "UP"}:
        return "BULLISH"
    if normalized in {"BEARISH", "SELL", "SHORT", "DOWN"}:
        return "BEARISH"
    return None


def _wilson_interval(successes: int, total: int) -> dict[str, float] | None:
    if total <= 0:
        return None
    z = 1.959963984540054
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt((p * (1 - p) / total) + (z * z / (4 * total * total))) / denominator
    return {"lower": max(0.0, center - margin), "upper": min(1.0, center + margin)}


def _signal_quality(rows: list[dict[str, Any]]) -> dict[str, Any]:
    predicted = [row for row in rows if row.get("signal_direction") in {"BULLISH", "BEARISH"}]
    correct = 0
    adverse = 0
    flat = 0
    for row in predicted:
        value = float(row["gross_return_percent"])
        aligned = value > 0 if row["signal_direction"] == "BULLISH" else value < 0
        opposed = value < 0 if row["signal_direction"] == "BULLISH" else value > 0
        correct += int(aligned)
        adverse += int(opposed)
        flat += int(value == 0)
    scored = correct + adverse
    hit_rate = correct / scored if scored else None
    return {
        "status": "DIRECTIONAL_HYPOTHESIS_AVAILABLE" if predicted else "NO_EXPLICIT_DIRECTIONAL_HYPOTHESIS",
        "prediction_count": len(predicted),
        "scored_non_flat_count": scored,
        "directional_hit_count": correct,
        "directional_miss_count": adverse,
        "flat_outcome_count": flat,
        "directional_hit_rate": hit_rate,
        "directional_hit_rate_ci_95_wilson": _wilson_interval(correct, scored),
        "false_positive_count": None,
        "false_negative_count": None,
        "false_positive_negative_limitation": (
            "Cannot be computed from selected directional snapshots alone. False positives/negatives require "
            "a defined binary event label and an evaluation universe that includes both signal and non-signal cases."
        ),
        "interpretation": (
            "Hit rate compares an explicitly stored BULLISH/BEARISH hypothesis with the sign of the subsequent "
            "gross close-to-close return. Flat outcomes are excluded from the hit-rate denominator. This is "
            "observational and does not include execution, fees, or a validated event label."
        ),
    }


class HistoricalSignalPerformance:
    """Evaluate forward price outcomes for stored descriptive snapshots; never infer trades."""

    HORIZONS_HOURS = (1, 4, 24)

    def __init__(self, signals: DerivativesSignalStore, klines: HistoricalKlineStore) -> None:
        self.signals = signals
        self.klines = klines

    def evaluate(
        self,
        symbol: str,
        period: str = "1h",
        price_interval: str = "1h",
        limit: int = 500,
        round_trip_cost_bps: float = 0.0,
    ) -> dict[str, Any]:
        symbol = symbol.strip().upper()
        if not symbol or len(symbol) > 40:
            raise ValueError("Invalid symbol")
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        if price_interval not in {"1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w", "1M"}:
            raise ValueError("Unsupported price interval")
        if not math.isfinite(round_trip_cost_bps) or not 0 <= round_trip_cost_bps <= 500:
            raise ValueError("round_trip_cost_bps must be between 0 and 500")

        history = self.signals.history(symbol, period=period, limit=limit)
        snapshots = history["snapshots"]
        if not snapshots:
            return {
                "status": "NO_STORED_SIGNALS", "market": "USD_M", "symbol": symbol,
                "period": period, "price_interval": price_interval,
                "evaluated_signal_count": 0, "horizons": {},
                "limitations": ["No locally stored completed descriptive signal snapshots were found."],
            }

        horizons: dict[str, list[dict[str, Any]]] = {
            str(hours): [] for hours in self.HORIZONS_HOURS
        }
        pending: dict[str, int] = {str(hours): 0 for hours in self.HORIZONS_HOURS}
        skipped_no_baseline = 0
        skipped_no_future = 0
        for snapshot in snapshots:
            analysis = snapshot["analysis"]
            signal_time = int(snapshot["end_time_ms"])
            signal_direction = _explicit_signal_direction(analysis)
            market_regime = (
                (analysis.get("market_regime") or {}).get("market_regime")
                or (analysis.get("regime") or {}).get("market_regime")
                or "UNCLASSIFIED"
            )
            # Baseline is the last candle fully closed at or before the snapshot timestamp.
            candles = self.klines.history(
                "USD_M", symbol, price_interval,
                start_time_ms=max(0, signal_time - 40 * 24 * 60 * 60 * 1000),
                end_time_ms=signal_time + 24 * 60 * 60 * 1000 + 40 * 24 * 60 * 60 * 1000,
                limit=5000,
            )["candles"]
            baseline_candidates = [c for c in candles if c["close_time_ms"] <= signal_time]
            future = [c for c in candles if c["open_time_ms"] >= signal_time]
            if not baseline_candidates:
                skipped_no_baseline += 1
                continue
            baseline = baseline_candidates[-1]
            base_price = float(baseline["close"])
            if not math.isfinite(base_price) or base_price <= 0:
                skipped_no_baseline += 1
                continue

            for hours in self.HORIZONS_HOURS:
                key = str(hours)
                target_ms = signal_time + hours * 60 * 60 * 1000
                eligible = [c for c in future if c["close_time_ms"] >= target_ms - 1]
                if not eligible:
                    pending[key] += 1
                    continue
                endpoint = eligible[0]
                window = [c for c in future if c["close_time_ms"] <= endpoint["close_time_ms"]]
                if not window:
                    pending[key] += 1
                    continue
                high = max(float(c["high"]) for c in window)
                low = min(float(c["low"]) for c in window)
                final_price = float(endpoint["close"])
                if not all(math.isfinite(v) and v > 0 for v in (high, low, final_price)):
                    continue
                gross = (final_price - base_price) / base_price * 100.0
                cost_percent = round_trip_cost_bps / 100.0
                horizons[key].append({
                    "signal_time_ms": signal_time,
                    "outcome_close_time_ms": int(endpoint["close_time_ms"]),
                    "actual_elapsed_hours": (int(endpoint["close_time_ms"]) - signal_time) / 3_600_000,
                    "baseline_close": base_price,
                    "outcome_close": final_price,
                    "gross_return_percent": gross,
                    "net_hypothetical_return_percent": gross - cost_percent,
                    "maximum_favorable_excursion_percent": (high - base_price) / base_price * 100.0,
                    "maximum_adverse_excursion_percent": (low - base_price) / base_price * 100.0,
                    "descriptive_classification": (
                        analysis.get("positioning_context", {}).get("classification")
                        or analysis.get("trend", {}).get("direction")
                        or "UNCLASSIFIED"
                    ),
                    "signal_direction": signal_direction,
                    "market_regime": str(market_regime),
                    "directional_outcome": (
                        "HIT" if signal_direction == "BULLISH" and gross > 0
                        or signal_direction == "BEARISH" and gross < 0
                        else "MISS" if signal_direction == "BULLISH" and gross < 0
                        or signal_direction == "BEARISH" and gross > 0
                        else "FLAT" if signal_direction and gross == 0
                        else "NOT_SCORABLE"
                    ),
                })

        summaries: dict[str, Any] = {}
        for key, rows in horizons.items():
            returns = [r["gross_return_percent"] for r in rows]
            net_returns = [r["net_hypothetical_return_percent"] for r in rows]
            signal_quality = _signal_quality(rows)
            regime_groups: dict[str, list[dict[str, Any]]] = {}
            for row in rows:
                regime_groups.setdefault(row["market_regime"], []).append(row)
            summaries[key] = {
                "horizon_hours": int(key),
                "signal_quality": signal_quality,
                "signal_quality_by_market_regime": {
                    regime: _signal_quality(group_rows)
                    for regime, group_rows in sorted(regime_groups.items())
                },
                "status": "COMPLETED" if rows else "INSUFFICIENT_FUTURE_DATA",
                "sample_size": len(rows),
                "pending_or_not_yet_matured": pending[key],
                "mean_gross_return_percent": sum(returns) / len(returns) if rows else None,
                "median_gross_return_percent": median(returns) if rows else None,
                "mean_net_hypothetical_return_percent": sum(net_returns) / len(net_returns) if rows else None,
                "positive_return_fraction": sum(value > 0 for value in returns) / len(returns) if rows else None,
                "mean_maximum_favorable_excursion_percent": (
                    sum(r["maximum_favorable_excursion_percent"] for r in rows) / len(rows) if rows else None
                ),
                "mean_maximum_adverse_excursion_percent": (
                    sum(r["maximum_adverse_excursion_percent"] for r in rows) / len(rows) if rows else None
                ),
                "outcomes": rows,
            }

        return {
            "status": "COMPLETED" if any(horizons.values()) else "INSUFFICIENT_FUTURE_DATA",
            "market": "USD_M", "symbol": symbol, "period": period,
            "price_interval": price_interval, "evaluated_signal_count": len(snapshots),
            "skipped_no_baseline": skipped_no_baseline,
            "round_trip_cost_bps_assumption": round_trip_cost_bps,
            "horizons": summaries,
            "method": {
                "baseline": "Last locally stored candle fully closed at or before the signal snapshot timestamp.",
                "future_endpoint": "First later candle whose close timestamp is at or after the requested horizon; actual elapsed time is reported.",
                "mfe_mae": "High/low excursion from baseline close across future candles through the selected endpoint.",
                "directional_accuracy": "Calculated only when a snapshot contains an explicit BULLISH/BEARISH signal_direction, directional_signal.direction, or confluence.bias; descriptive OI classifications are never converted into predictions.",
                "fees_and_slippage": "Only the caller-supplied round-trip basis-point deduction is applied; this is not actual execution cost.",
            },
            "limitations": [
                "This is an observational forward-outcome study of stored snapshots, not a trading strategy backtest.",
                "Directional hit rate is reported only for snapshots with an explicit directional hypothesis; positive-return fraction is not signal hit rate. False-positive/false-negative counts require a binary event label and non-signal evaluation universe and are therefore withheld.",
                "Results depend on local candle coverage and may be biased by missing or selectively collected snapshots.",
                "No market impact, funding payments, liquidation, position sizing, leverage, or execution simulation is included.",
                "The selected candle close can occur after the exact requested horizon; actual elapsed time is included.",
                "Historical outcomes do not establish future performance.",
            ],
            "source": "Locally stored USD-M derivatives snapshots and historical OHLCV candles.",
        }
