from __future__ import annotations

import math
from typing import Any

from app.services.funding_rates import FundingRateStore
from app.services.historical_klines import HistoricalKlineStore
from app.services.open_interest import OPEN_INTEREST_PERIODS, OpenInterestStore


def _percent_change(first: float, last: float) -> float | None:
    if not math.isfinite(first) or not math.isfinite(last) or first == 0:
        return None
    return ((last - first) / abs(first)) * 100.0


class FundingOpenInterestAnalysis:
    """Explain co-movement in locally stored USD-M price, OI and funding data."""

    def __init__(
        self, funding_store: FundingRateStore, open_interest_store: OpenInterestStore,
        kline_store: HistoricalKlineStore,
    ) -> None:
        self.funding_store = funding_store
        self.open_interest_store = open_interest_store
        self.kline_store = kline_store

    def analyze(
        self, symbol: str, period: str = "1h", price_interval: str = "1h",
        limit: int = 24,
    ) -> dict[str, Any]:
        symbol = symbol.strip().upper()
        if not symbol or len(symbol) > 40:
            raise ValueError("symbol must be a non-empty symbol up to 40 characters")
        if period not in OPEN_INTEREST_PERIODS:
            raise ValueError("Unsupported open-interest period")
        if not price_interval or len(price_interval) > 5:
            raise ValueError("Invalid price interval")
        if not 2 <= limit <= 500:
            raise ValueError("limit must be between 2 and 500")

        oi_result = self.open_interest_store.history(
            "USD_M", symbol, period=period, limit=limit,
        )
        oi_rows = oi_result["records"]
        if len(oi_rows) < 2:
            return {
                "status": "INSUFFICIENT_DATA", "market": "USD_M", "symbol": symbol,
                "period": period, "price_interval": price_interval,
                "required_open_interest_records": 2,
                "available_open_interest_records": len(oi_rows),
                "analysis": None,
                "limitations": [
                    "At least two locally stored open-interest records are required.",
                    "This analysis never treats open interest alone as a directional long/short position count.",
                ],
            }

        first_oi, last_oi = oi_rows[0], oi_rows[-1]
        oi_change = last_oi["sum_open_interest"] - first_oi["sum_open_interest"]
        oi_change_pct = _percent_change(
            first_oi["sum_open_interest"], last_oi["sum_open_interest"]
        )
        oi_value_change_pct = _percent_change(
            first_oi["sum_open_interest_value"], last_oi["sum_open_interest_value"]
        )

        start_ms, end_ms = first_oi["timestamp_ms"], last_oi["timestamp_ms"]
        price_result = self.kline_store.history(
            "USD_M", symbol, price_interval,
            start_time_ms=start_ms, end_time_ms=end_ms, limit=5000,
        )
        candles = price_result["candles"]
        price_change_pct = (
            _percent_change(candles[0]["close"], candles[-1]["close"])
            if len(candles) >= 2 else None
        )

        funding_result = self.funding_store.history(
            "USD_M", symbol, start_time_ms=start_ms, end_time_ms=end_ms, limit=5000,
        )
        funding_events = funding_result["events"]
        funding_rates = [float(event["funding_rate"]) for event in funding_events]
        mean_funding = sum(funding_rates) / len(funding_rates) if funding_rates else None
        positive_count = sum(rate > 0 for rate in funding_rates)
        negative_count = sum(rate < 0 for rate in funding_rates)

        oi_direction = "INCREASING" if oi_change > 0 else "DECREASING" if oi_change < 0 else "FLAT"
        price_direction = (
            "UP" if price_change_pct is not None and price_change_pct > 0
            else "DOWN" if price_change_pct is not None and price_change_pct < 0
            else "FLAT" if price_change_pct is not None else "UNAVAILABLE"
        )
        if price_direction == "UNAVAILABLE":
            interpretation = "PRICE_CONTEXT_UNAVAILABLE"
        elif oi_direction == "INCREASING" and price_direction == "UP":
            interpretation = "PRICE_UP_WITH_OI_UP_POSITION_BUILDUP_CANDIDATE"
        elif oi_direction == "INCREASING" and price_direction == "DOWN":
            interpretation = "PRICE_DOWN_WITH_OI_UP_POSITION_BUILDUP_CANDIDATE"
        elif oi_direction == "DECREASING":
            interpretation = "OPEN_INTEREST_CONTRACTION_OR_POSITION_CLOSING"
        else:
            interpretation = "MIXED_OR_FLAT_CONDITIONS"

        if mean_funding is None:
            funding_bias = "UNAVAILABLE"
        elif mean_funding > 0:
            funding_bias = "POSITIVE_FUNDING_LONGS_PAY_SHORTS"
        elif mean_funding < 0:
            funding_bias = "NEGATIVE_FUNDING_SHORTS_PAY_LONGS"
        else:
            funding_bias = "NEAR_ZERO_FUNDING"

        return {
            "status": "COMPLETED", "market": "USD_M", "symbol": symbol,
            "period": period, "price_interval": price_interval, "window": {
                "start_time_ms": start_ms, "end_time_ms": end_ms,
                "open_interest_records": len(oi_rows),
                "price_candles": len(candles), "funding_events": len(funding_events),
            },
            "metrics": {
                "open_interest": {
                    "first": first_oi["sum_open_interest"],
                    "last": last_oi["sum_open_interest"],
                    "absolute_change": oi_change,
                    "change_percent": oi_change_pct,
                    "value_change_percent": oi_value_change_pct,
                    "direction": oi_direction,
                },
                "price": {
                    "first_close": candles[0]["close"] if candles else None,
                    "last_close": candles[-1]["close"] if candles else None,
                    "change_percent": price_change_pct,
                    "direction": price_direction,
                },
                "funding": {
                    "event_count": len(funding_rates),
                    "latest_rate": funding_rates[-1] if funding_rates else None,
                    "mean_rate": mean_funding,
                    "positive_event_count": positive_count,
                    "negative_event_count": negative_count,
                    "bias": funding_bias,
                },
            },
            "interpretation": {
                "code": interpretation,
                "summary": (
                    "Open interest increased while price rose; this can indicate new positioning, "
                    "but does not identify whether the increase is driven by longs or shorts."
                    if interpretation == "PRICE_UP_WITH_OI_UP_POSITION_BUILDUP_CANDIDATE"
                    else "Open interest increased while price fell; this can indicate new positioning, "
                    "but does not identify whether the increase is driven by longs or shorts."
                    if interpretation == "PRICE_DOWN_WITH_OI_UP_POSITION_BUILDUP_CANDIDATE"
                    else "Open interest fell over the selected window; this is consistent with position closing or deleveraging, but does not identify which side closed."
                    if interpretation == "OPEN_INTEREST_CONTRACTION_OR_POSITION_CLOSING"
                    else "Price history is unavailable for the selected stored window."
                    if interpretation == "PRICE_CONTEXT_UNAVAILABLE"
                    else "The selected data do not show a clear price/open-interest directional combination."
                ),
                "funding_bias": funding_bias,
            },
            "limitations": [
                "This is descriptive analysis of locally stored records, not a prediction or trading signal.",
                "Aggregate open interest does not reveal the number of long versus short traders or identify which side opened positions.",
                "Price and open-interest windows may contain missing or differently timed observations.",
                "Funding statistics include only locally stored events within the open-interest time window.",
                "No liquidation, order-book, or account-level positioning data is inferred.",
            ],
            "sources": {
                "open_interest": oi_result["source"],
                "price": price_result["source"],
                "funding": funding_result["source"],
            },
        }
