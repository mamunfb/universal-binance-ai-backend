from __future__ import annotations

from typing import Any

from app.services.advanced_derivatives_analysis import AdvancedDerivativesAnalysis

SUPPORTED_PERIODS = ("5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d")


class MultiTimeframeDerivativesAnalysis:
    """Combine independent local OI analyses without claiming synchronized timestamps."""

    def __init__(self, engine: AdvancedDerivativesAnalysis) -> None:
        self.engine = engine

    def analyze(
        self, symbol: str, periods: list[str] | None = None,
        limit: int = 48,
    ) -> dict[str, Any]:
        symbol = symbol.strip().upper()
        if not symbol or len(symbol) > 40:
            raise ValueError("Invalid symbol")
        periods = ["5m", "15m", "1h", "4h", "1d"] if periods is None else periods
        if not isinstance(periods, list) or not 1 <= len(periods) <= 9:
            raise ValueError("periods must contain between 1 and 9 entries")
        if any(not isinstance(p, str) or p not in SUPPORTED_PERIODS for p in periods):
            raise ValueError("Unsupported open-interest period")
        if len(set(periods)) != len(periods):
            raise ValueError("Duplicate periods are not allowed")
        if not 6 <= limit <= 500:
            raise ValueError("limit must be between 6 and 500")

        sections: dict[str, Any] = {}
        for period in periods:
            # The same interval is used for price and OI within each timeframe.
            # Historical price observations may still have different timestamps.
            result = self.engine.analyze(symbol, period, period, limit)
            sections[period] = result

        completed = {
            period: result for period, result in sections.items()
            if result["status"] == "COMPLETED"
        }
        rising = [
            period for period, result in completed.items()
            if result["trend"]["direction"] == "OI_RISING"
        ]
        falling = [
            period for period, result in completed.items()
            if result["trend"]["direction"] == "OI_FALLING"
        ]
        flat = [
            period for period, result in completed.items()
            if result["trend"]["direction"] == "OI_FLAT"
        ]
        unavailable = [period for period in periods if period not in completed]
        endpoints = [
            result["window"]["end_time_ms"] for result in completed.values()
        ]
        aligned = len(endpoints) >= 2 and len(set(endpoints)) == 1
        if not completed:
            status = "INSUFFICIENT_DATA"
            agreement = "UNAVAILABLE"
        elif unavailable:
            status = "INCOMPLETE"
            agreement = "INCOMPLETE_COVERAGE"
        else:
            status = "COMPLETED"
            if len(completed) == 1:
                agreement = "SINGLE_TIMEFRAME_ONLY"
            elif not aligned:
                agreement = "UNALIGNED_END_TIMESTAMPS"
            elif len(rising) == len(completed):
                agreement = "ALL_OI_RISING"
            elif len(falling) == len(completed):
                agreement = "ALL_OI_FALLING"
            elif len(flat) == len(completed):
                agreement = "ALL_OI_FLAT"
            else:
                agreement = "MIXED_OI_DIRECTIONS"

        return {
            "status": status,
            "market": "USD_M",
            "symbol": symbol,
            "requested_periods": periods,
            "completed_periods": list(completed),
            "missing_periods": unavailable,
            "timeframe_agreement": {
                "classification": agreement,
                "end_timestamps_identical": aligned,
                "rising_periods": rising,
                "falling_periods": falling,
                "flat_periods": flat,
                "end_time_ms_by_period": {
                    period: result["window"]["end_time_ms"]
                    for period, result in completed.items()
                },
            },
            "sections": sections,
            "limitations": [
                "Each timeframe uses its own locally stored records and may cover a different historical window.",
                "Agreement is withheld if latest OI timestamps differ; missing periods cannot confirm a market regime.",
                "Even matching end timestamps do not establish full price/OI candle alignment or complete coverage.",
                "This is descriptive market research, not a trading signal, prediction, or calibrated confidence score.",
                "Running this analysis writes individual completed timeframe snapshots to local signal history.",
            ],
        }
