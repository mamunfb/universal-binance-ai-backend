from __future__ import annotations

import math
from statistics import median
from typing import Any

from app.services.historical_klines import HistoricalKlineStore


class MarketRegimeAnalysis:
    """Transparent descriptive regime heuristic over locally stored OHLC candles."""

    WINDOW = 20
    MIN_BASELINE_WINDOWS = 5

    def __init__(self, history: HistoricalKlineStore) -> None:
        self.history = history

    @staticmethod
    def _true_range_percent(candle: dict[str, Any], previous_close: float) -> float:
        high, low, close = float(candle["high"]), float(candle["low"]), float(candle["close"])
        true_range = max(high - low, abs(high - previous_close), abs(low - previous_close))
        value = true_range / close * 100.0
        if not math.isfinite(value):
            raise ValueError("Non-finite candle range")
        return value

    def analyze(
        self, market: str, symbol: str, interval: str, limit: int = 200
    ) -> dict[str, Any]:
        market = market.upper().strip()
        symbol = symbol.upper().strip()
        if market not in {"SPOT", "USD_M", "COIN_M"}:
            raise ValueError("market must be SPOT, USD_M, or COIN_M")
        if not symbol or len(symbol) > 40:
            raise ValueError("Invalid symbol")
        if not interval or len(interval) > 4:
            raise ValueError("Invalid interval")
        if not 40 <= limit <= 1000:
            raise ValueError("limit must be between 40 and 1000")

        candles = self.history.history(market, symbol, interval, limit=limit)["candles"]
        if len(candles) < 40:
            return {
                "status": "INSUFFICIENT_DATA", "market": market, "symbol": symbol,
                "interval": interval, "required_candles": 40,
                "available_candles": len(candles),
                "market_regime": "UNKNOWN",
                "limitations": ["At least 40 locally stored candles are required."],
            }

        closes = [float(row["close"]) for row in candles]
        if any(not math.isfinite(value) or value <= 0 for value in closes):
            raise ValueError("Stored close prices must be finite and positive")
        trp = [
            self._true_range_percent(candles[index], closes[index - 1])
            for index in range(1, len(candles))
        ]
        rolling = [
            sum(trp[index - self.WINDOW:index]) / self.WINDOW
            for index in range(self.WINDOW, len(trp) + 1)
        ]
        latest_volatility = rolling[-1]
        baseline = rolling[:-1]
        if len(baseline) < self.MIN_BASELINE_WINDOWS:
            return {
                "status": "INSUFFICIENT_BASELINE", "market": market, "symbol": symbol,
                "interval": interval, "market_regime": "UNKNOWN",
                "latest_range_percent": latest_volatility,
                "baseline_windows": len(baseline),
                "limitations": ["At least five prior 20-candle volatility windows are required."],
            }

        baseline_median = median(baseline)
        if baseline_median <= 0:
            volatility_regime = "UNKNOWN"
        elif latest_volatility > baseline_median * 1.5:
            volatility_regime = "HIGH_VOLATILITY"
        elif latest_volatility < baseline_median * 0.5:
            volatility_regime = "LOW_VOLATILITY"
        else:
            volatility_regime = "NORMAL_VOLATILITY"

        recent = closes[-self.WINDOW:]
        path_length = sum(abs(recent[i] - recent[i - 1]) for i in range(1, len(recent)))
        efficiency = abs(recent[-1] - recent[0]) / path_length if path_length > 0 else 0.0
        direction = (
            "UP" if recent[-1] > recent[0]
            else "DOWN" if recent[-1] < recent[0]
            else "FLAT"
        )
        structure_regime = "TREND" if efficiency >= 0.60 else "RANGE"

        if volatility_regime in {"HIGH_VOLATILITY", "LOW_VOLATILITY"}:
            regime = volatility_regime
        elif volatility_regime == "UNKNOWN":
            regime = "UNKNOWN"
        else:
            regime = structure_regime

        return {
            "status": "COMPLETED",
            "market": market, "symbol": symbol, "interval": interval,
            "market_regime": regime,
            "volatility_regime": volatility_regime,
            "structure_regime": structure_regime,
            "directional_context": direction,
            "metrics": {
                "latest_20_candle_mean_true_range_percent": latest_volatility,
                "prior_window_median_true_range_percent": baseline_median,
                "volatility_ratio_to_baseline": (
                    latest_volatility / baseline_median if baseline_median > 0 else None
                ),
                "20_candle_path_efficiency": efficiency,
                "candles_used": len(candles),
            },
            "window": {
                "start_time_ms": candles[-self.WINDOW]["open_time_ms"],
                "end_time_ms": candles[-1]["open_time_ms"],
                "baseline_windows": len(baseline),
            },
            "methodology": {
                "volatility": "Mean true range divided by close over rolling 20-candle windows.",
                "high_volatility_rule": "Latest window is more than 1.5x prior-window median.",
                "low_volatility_rule": "Latest window is less than 0.5x prior-window median.",
                "structure": "Absolute net close move divided by total absolute close-to-close path; TREND at >=0.60, otherwise RANGE.",
                "priority": "HIGH_VOLATILITY or LOW_VOLATILITY overrides TREND/RANGE as the primary regime.",
            },
            "limitations": [
                "This is a deterministic descriptive heuristic, not a statistically calibrated classifier.",
                "Thresholds are fixed rules and have not been optimized or validated for predictive performance.",
                "Regime labels depend on the locally stored candle sample and can change as new candles arrive.",
                "No future price direction, probability, or trading signal is inferred.",
            ],
        }
