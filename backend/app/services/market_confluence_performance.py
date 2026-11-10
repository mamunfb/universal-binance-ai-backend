from __future__ import annotations

import math
from typing import Any

from app.services.historical_klines import HistoricalKlineStore
from app.services.market_confluence_store import MarketConfluenceStore


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
        summaries: dict[str, Any] = {}
        for hours in self.HORIZONS_HOURS:
            outcomes = []
            pending = missing_reference = 0
            horizon_ms = hours * 3_600_000
            for snapshot in history["snapshots"]:
                analyzed_at = int(snapshot["analyzed_at_ms"])
                reference = snapshot["reference_price"]
                bias = snapshot["bias"]
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
            summaries[str(hours)] = {
                "label": self.HORIZON_LABELS[hours],
                "horizon_hours": hours,
                "horizon_days": hours / 24,
                "status": "COMPLETED" if outcomes else "INSUFFICIENT_FUTURE_DATA",
                "sample_size": len(outcomes),
                "directional_sample_size": len(directional),
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
                "mfe_mae": "Directional high/low excursion; not a stop/target simulation.",
                "coverage": "Every outcome reports whether the local candle sequence is continuous from the first expected candle through its endpoint.",
            },
            "limitations": [
                "Local history only; missing candles are not interpolated or backfilled.",
                "A horizon is evaluated only when a stored candle closes at or after its target time.",
                "No execution, fees, slippage, funding, leverage, position sizing, stop or target is simulated.",
                "Not strategy profitability, investment advice, or a forecast.",
            ],
        }
