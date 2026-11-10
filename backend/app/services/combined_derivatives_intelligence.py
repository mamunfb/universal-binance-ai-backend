from __future__ import annotations

from typing import Any

from app.services.funding_rates import FundingRateStore
from app.services.open_interest import OPEN_INTEREST_PERIODS, OpenInterestStore
from app.services.derivatives_ratio_store import DerivativesRatioStore


class CombinedDerivativesIntelligence:
    """Join stored OI, account-ratio and taker-ratio evidence conservatively."""

    def __init__(
        self, open_interest: OpenInterestStore, funding: FundingRateStore,
        ratios: DerivativesRatioStore,
    ) -> None:
        self.open_interest = open_interest
        self.funding = funding
        self.ratios = ratios

    def analyze(self, symbol: str, period: str = "1h", limit: int = 100) -> dict[str, Any]:
        symbol = symbol.strip().upper()
        if not symbol or len(symbol) > 40:
            raise ValueError("Invalid symbol")
        if period not in OPEN_INTEREST_PERIODS:
            raise ValueError("Unsupported derivatives period")
        if not 2 <= limit <= 500:
            raise ValueError("limit must be between 2 and 500")

        oi = self.open_interest.history("USD_M", symbol, period, limit=limit)["records"]
        global_ratio = self.ratios.history(
            "GLOBAL_LONG_SHORT", symbol, period, limit=limit
        )["records"]
        taker_ratio = self.ratios.history(
            "TAKER_BUY_SELL", symbol, period, limit=limit
        )["records"]

        oi_by_time = {row["timestamp_ms"]: row for row in oi}
        global_by_time = {row["timestamp_ms"]: row for row in global_ratio}
        taker_by_time = {row["timestamp_ms"]: row for row in taker_ratio}
        common_times = sorted(set(oi_by_time) & set(global_by_time) & set(taker_by_time))
        joined = [{
            "timestamp_ms": timestamp,
            "open_interest": oi_by_time[timestamp]["sum_open_interest"],
            "open_interest_value": oi_by_time[timestamp]["sum_open_interest_value"],
            "global_long_short_ratio": global_by_time[timestamp]["long_short_ratio"],
            "long_account_fraction": global_by_time[timestamp]["long_account"],
            "short_account_fraction": global_by_time[timestamp]["short_account"],
            "taker_buy_sell_ratio": taker_by_time[timestamp]["buy_sell_ratio"],
            "taker_buy_volume": taker_by_time[timestamp]["buy_volume"],
            "taker_sell_volume": taker_by_time[timestamp]["sell_volume"],
        } for timestamp in common_times]

        funding_events = self.funding.history(
            "USD_M", symbol,
            start_time_ms=oi[0]["timestamp_ms"] if oi else None,
            end_time_ms=oi[-1]["timestamp_ms"] if oi else None,
            limit=5000,
        )["events"] if oi else []

        latest_funding = funding_events[-1] if funding_events else None
        if len(joined) < 2:
            return {
                "status": "INSUFFICIENT_ALIGNED_DATA",
                "market": "USD_M", "symbol": symbol, "period": period,
                "coverage": {
                    "open_interest_records": len(oi),
                    "global_ratio_records": len(global_ratio),
                    "taker_ratio_records": len(taker_ratio),
                    "exact_timestamp_matches": len(joined),
                    "required_matches": 2,
                },
                "aligned_observations": joined,
                "funding": {
                    "status": "AVAILABLE" if latest_funding else "NO_STORED_FUNDING",
                    "latest_event": latest_funding,
                },
                "limitations": [
                    "At least two exact timestamp matches across OI, global account ratio and taker ratio are required.",
                    "Missing or differently timestamped observations are not forward-filled or interpolated.",
                    "Funding events are sparse and are reported separately, not falsely aligned to every ratio interval.",
                ],
            }

        first, last = joined[0], joined[-1]
        oi_change = self._pct(first["open_interest"], last["open_interest"])
        global_change = self._pct(first["global_long_short_ratio"], last["global_long_short_ratio"])
        taker_change = self._pct(first["taker_buy_sell_ratio"], last["taker_buy_sell_ratio"])
        if last["global_long_short_ratio"] > 1:
            account_bias = "MORE_LONG_ACCOUNTS_THAN_SHORT_ACCOUNTS"
        elif last["global_long_short_ratio"] < 1:
            account_bias = "MORE_SHORT_ACCOUNTS_THAN_LONG_ACCOUNTS"
        else:
            account_bias = "EQUAL_ACCOUNT_RATIO"
        if last["taker_buy_sell_ratio"] > 1:
            taker_pressure = "MORE_AGGRESSIVE_BUY_VOLUME"
        elif last["taker_buy_sell_ratio"] < 1:
            taker_pressure = "MORE_AGGRESSIVE_SELL_VOLUME"
        else:
            taker_pressure = "BALANCED_TAKER_VOLUME"

        return {
            "status": "COMPLETED",
            "market": "USD_M", "symbol": symbol, "period": period,
            "coverage": {
                "open_interest_records": len(oi),
                "global_ratio_records": len(global_ratio),
                "taker_ratio_records": len(taker_ratio),
                "exact_timestamp_matches": len(joined),
                "first_aligned_timestamp_ms": first["timestamp_ms"],
                "last_aligned_timestamp_ms": last["timestamp_ms"],
                "funding_events_in_oi_window": len(funding_events),
            },
            "changes_over_aligned_window": {
                "open_interest_percent": oi_change,
                "global_long_short_ratio_percent": global_change,
                "taker_buy_sell_ratio_percent": taker_change,
            },
            "latest_positioning_observations": {
                "global_long_short_ratio": last["global_long_short_ratio"],
                "long_account_fraction": last["long_account_fraction"],
                "short_account_fraction": last["short_account_fraction"],
                "account_count_comparison": account_bias,
                "taker_buy_sell_ratio": last["taker_buy_sell_ratio"],
                "taker_volume_comparison": taker_pressure,
                "open_interest": last["open_interest"],
            },
            "funding": {
                "status": "AVAILABLE" if latest_funding else "NO_STORED_FUNDING",
                "latest_event": latest_funding,
                "note": "Funding event is shown separately because its schedule is not the same as the ratio sampling interval.",
            },
            "aligned_observations": joined,
            "interpretation_warnings": [
                "Global long/short ratio compares account counts, not position size or leverage.",
                "Taker buy/sell ratio measures aggressive trade volume, not all trading activity or guaranteed price direction.",
                "Open interest is aggregate matched contracts and cannot identify which side initiated positions.",
                "These indicators are descriptive and do not constitute a trading signal or calibrated probability.",
                "Only exact timestamp intersections are included; missing data is not filled, interpolated or assumed.",
            ],
        }

    @staticmethod
    def _pct(first: float, last: float) -> float | None:
        if first == 0:
            return None
        return (last - first) / abs(first) * 100.0
