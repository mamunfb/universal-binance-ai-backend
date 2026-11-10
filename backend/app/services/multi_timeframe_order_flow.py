from __future__ import annotations

from typing import Any

from app.services.order_flow_intelligence import analyze_order_flow

PERIOD_MINUTES = {
    "5m": 5, "15m": 15, "30m": 30, "1h": 60,
    "2h": 120, "4h": 240, "6h": 360, "12h": 720, "1d": 1440,
}


def analyze_multi_timeframe_order_flow(
    trades: list[dict[str, Any]],
    market: str,
    symbol: str,
    end_time_ms: int,
    periods: list[str] | tuple[str, ...] = ("5m", "15m", "1h", "4h", "1d"),
    bin_size_bps: float = 5.0,
    value_area_pct: float = 70.0,
) -> dict[str, Any]:
    """Compare independent rolling windows of locally stored aggregate trade flow."""
    if end_time_ms < 0:
        raise ValueError("end_time_ms must be non-negative")
    if not periods or len(periods) > 9:
        raise ValueError("Select between 1 and 9 timeframes")
    normalized = [str(period).strip() for period in periods]
    if len(set(normalized)) != len(normalized):
        raise ValueError("Timeframes must be unique")
    unsupported = [period for period in normalized if period not in PERIOD_MINUTES]
    if unsupported:
        raise ValueError(f"Unsupported timeframes: {', '.join(unsupported)}")

    analyses = []
    for period in normalized:
        start_time_ms = max(0, end_time_ms - PERIOD_MINUTES[period] * 60_000)
        result = analyze_order_flow(
            trades, market, symbol, start_time_ms, end_time_ms,
            bin_size_bps, value_area_pct,
        )
        flow = result.get("aggressor_flow", {})
        divergence = result.get("price_cvd_divergence", {})
        profile = result.get("volume_profile", {})
        analyses.append({
            "period": period,
            "window_start_time_ms": start_time_ms,
            "window_end_time_ms": end_time_ms,
            "status": result["status"],
            "trade_count": result["trade_count"],
            "observed_window": result.get("observed_window"),
            "net_cvd_quantity": flow.get("net_cvd_quantity"),
            "net_cvd_notional_proxy": flow.get("net_cvd_notional_proxy"),
            "buy_sell_quantity_imbalance": flow.get("buy_sell_quantity_imbalance"),
            "price_cvd_divergence": divergence.get("classification"),
            "poc": profile.get("poc"),
            "value_area": profile.get("value_area"),
            "coverage": result.get("coverage"),
        })

    complete = [item for item in analyses if item["status"] == "COMPLETED"]
    directional = []
    for item in complete:
        cvd = item["net_cvd_quantity"]
        if cvd is not None and cvd > 0:
            directional.append("BUY")
        elif cvd is not None and cvd < 0:
            directional.append("SELL")
        else:
            directional.append("FLAT")
    if len(complete) != len(analyses):
        agreement = "INSUFFICIENT_TIMEFRAME_DATA"
    elif len(set(directional)) == 1:
        agreement = f"ALL_TIMEFRAMES_{directional[0]}_CVD"
    elif len(set(directional)) == 2 and "FLAT" not in directional:
        agreement = "MIXED_BUY_SELL_CVD"
    else:
        agreement = "MIXED_OR_FLAT_CVD"

    return {
        "status": "COMPLETED" if complete else "INSUFFICIENT_DATA",
        "market": market.upper(), "symbol": symbol.upper(),
        "as_of_time_ms": end_time_ms,
        "requested_periods": normalized,
        "timeframe_count": len(analyses),
        "completed_timeframe_count": len(complete),
        "cvd_agreement": agreement,
        "timeframes": analyses,
        "interpretation": (
            "Agreement describes the sign of observed window-relative CVD only. "
            "Different rolling windows overlap and are not independent confirmations."
        ),
        "warnings": [
            "Every timeframe uses locally captured aggregate trades and is calculated independently over its own rolling window.",
            "A timeframe marked COMPLETED may still have incomplete exchange coverage due to collector downtime or the query cap.",
            "CVD agreement is descriptive and does not establish trend direction, participant identity, institutional activity, or a trade signal.",
            "POC and value area levels are window- and bin-size-dependent observed notional proxies.",
            "COIN_M notional fields remain raw price-times-contract-quantity proxies without contract face-value conversion.",
        ],
    }
