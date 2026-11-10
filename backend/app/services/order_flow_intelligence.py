from __future__ import annotations

import math
from collections import defaultdict
from typing import Any


def analyze_order_flow(
    trades: list[dict[str, Any]],
    market: str,
    symbol: str,
    start_time_ms: int,
    end_time_ms: int,
    bin_size_bps: float = 5.0,
    value_area_pct: float = 70.0,
) -> dict[str, Any]:
    """Build a descriptive volume profile, CVD and price/flow divergence candidates."""
    market, symbol = market.upper(), symbol.upper()
    if market not in {"SPOT", "USD_M", "COIN_M"}:
        raise ValueError("market must be SPOT, USD_M or COIN_M")
    if not symbol or len(symbol) > 40:
        raise ValueError("Invalid symbol")
    if start_time_ms < 0 or end_time_ms < start_time_ms:
        raise ValueError("Require 0 <= start_time_ms <= end_time_ms")
    if not math.isfinite(bin_size_bps) or not 0.1 <= bin_size_bps <= 500:
        raise ValueError("bin_size_bps must be between 0.1 and 500")
    if not math.isfinite(value_area_pct) or not 50 <= value_area_pct <= 99:
        raise ValueError("value_area_pct must be between 50 and 99")

    valid: list[dict[str, Any]] = []
    rejected = 0
    for row in trades:
        try:
            timestamp = int(row["trade_time_ms"])
            price = float(row["price"])
            quantity = float(row["quantity"])
            notional = float(row.get("notional", price * quantity))
            side = str(row["aggressor_side"]).upper()
        except (KeyError, TypeError, ValueError, OverflowError):
            rejected += 1
            continue
        if (timestamp < start_time_ms or timestamp > end_time_ms or price <= 0
                or quantity <= 0 or notional <= 0
                or not all(math.isfinite(x) for x in (price, quantity, notional))
                or side not in {"BUY", "SELL"}):
            rejected += 1
            continue
        valid.append({
            "trade_time_ms": timestamp, "price": price, "quantity": quantity,
            "notional": notional, "aggressor_side": side,
        })
    valid.sort(key=lambda x: x["trade_time_ms"])
    base = {
        "market": market, "symbol": symbol, "requested_window": {
            "start_time_ms": start_time_ms, "end_time_ms": end_time_ms,
            "duration_ms": end_time_ms - start_time_ms,
        },
        "trade_count": len(valid), "rejected_trade_count": rejected,
        "method": "Locally captured Binance aggregate trades; aggressor side inferred from buyer-is-maker flag",
    }
    if not valid:
        return {**base, "status": "INSUFFICIENT_DATA", "reason": "NO_VALID_STORED_TRADES_IN_WINDOW"}

    reference_price = valid[0]["price"]
    price_step = reference_price * bin_size_bps / 10000.0
    if price_step <= 0 or not math.isfinite(price_step):
        raise ValueError("Could not derive a valid price bucket width")

    buckets: dict[int, dict[str, float]] = defaultdict(
        lambda: {"buy_quantity": 0.0, "sell_quantity": 0.0,
                 "buy_notional": 0.0, "sell_notional": 0.0, "trade_count": 0}
    )
    buy_qty = sell_qty = buy_notional = sell_notional = 0.0
    cvd_qty = cvd_notional = 0.0
    cvd_points: list[dict[str, float | int]] = []
    for trade in valid:
        index = math.floor((trade["price"] - reference_price) / price_step)
        bucket = buckets[index]
        side = trade["aggressor_side"]
        if side == "BUY":
            buy_qty += trade["quantity"]
            buy_notional += trade["notional"]
            bucket["buy_quantity"] += trade["quantity"]
            bucket["buy_notional"] += trade["notional"]
            cvd_qty += trade["quantity"]
            cvd_notional += trade["notional"]
        else:
            sell_qty += trade["quantity"]
            sell_notional += trade["notional"]
            bucket["sell_quantity"] += trade["quantity"]
            bucket["sell_notional"] += trade["notional"]
            cvd_qty -= trade["quantity"]
            cvd_notional -= trade["notional"]
        bucket["trade_count"] += 1
        cvd_points.append({
            "trade_time_ms": trade["trade_time_ms"],
            "cvd_quantity": cvd_qty,
            "cvd_notional_proxy": cvd_notional,
        })

    profile_rows = []
    for index, values in buckets.items():
        low = reference_price + index * price_step
        high = low + price_step
        total_notional = values["buy_notional"] + values["sell_notional"]
        profile_rows.append({
            "price_low": low, "price_high": high, "price_mid": (low + high) / 2,
            **values, "total_quantity": values["buy_quantity"] + values["sell_quantity"],
            "total_notional_proxy": total_notional,
        })
    profile_rows.sort(key=lambda row: row["price_low"])
    poc_index = max(buckets, key=lambda idx: (
        buckets[idx]["buy_notional"] + buckets[idx]["sell_notional"], -idx
    ))
    total_profile_notional = sum(
        row["total_notional_proxy"] for row in profile_rows
    )
    target_value = total_profile_notional * value_area_pct / 100.0
    selected = {poc_index}
    accumulated = (
        buckets[poc_index]["buy_notional"] + buckets[poc_index]["sell_notional"]
    )
    ordered_bucket_indices = sorted(buckets)
    poc_position = ordered_bucket_indices.index(poc_index)
    low_position = high_position = poc_position
    while accumulated < target_value and len(selected) < len(buckets):
        candidates = []
        for position in (low_position - 1, high_position + 1):
            if 0 <= position < len(ordered_bucket_indices):
                candidate = ordered_bucket_indices[position]
                if candidate not in selected:
                    value = buckets[candidate]["buy_notional"] + buckets[candidate]["sell_notional"]
                    candidates.append((value, position, candidate))
        if not candidates:
            break
        value, chosen_position, chosen = max(candidates, key=lambda item: (item[0], -item[2]))
        selected.add(chosen)
        accumulated += value
        low_position = min(low_position, chosen_position)
        high_position = max(high_position, chosen_position)
    low_idx = ordered_bucket_indices[low_position]
    high_idx = ordered_bucket_indices[high_position]

    first_price, last_price = valid[0]["price"], valid[-1]["price"]
    price_change_pct = (last_price - first_price) / first_price * 100.0
    net_cvd_qty = buy_qty - sell_qty
    net_cvd_notional = buy_notional - sell_notional
    if price_change_pct > 0 and net_cvd_qty < 0:
        divergence = "PRICE_UP_CVD_DOWN_CANDIDATE"
    elif price_change_pct < 0 and net_cvd_qty > 0:
        divergence = "PRICE_DOWN_CVD_UP_CANDIDATE"
    else:
        divergence = "NO_OPPOSING_PRICE_CVD_DIVERGENCE"
    total_qty = buy_qty + sell_qty
    total_notional = buy_notional + sell_notional
    return {
        **base, "status": "COMPLETED",
        "observed_window": {
            "first_trade_time_ms": valid[0]["trade_time_ms"],
            "last_trade_time_ms": valid[-1]["trade_time_ms"],
            "first_trade_price": first_price, "last_trade_price": last_price,
            "price_change_pct": price_change_pct,
        },
        "aggressor_flow": {
            "buy_quantity": buy_qty, "sell_quantity": sell_qty,
            "net_cvd_quantity": net_cvd_qty,
            "buy_notional_proxy": buy_notional, "sell_notional_proxy": sell_notional,
            "net_cvd_notional_proxy": net_cvd_notional,
            "buy_sell_quantity_imbalance": (buy_qty - sell_qty) / total_qty if total_qty else None,
            "buy_sell_notional_imbalance": (buy_notional - sell_notional) / total_notional if total_notional else None,
            "total_notional_proxy": total_notional,
        },
        "volume_profile": {
            "price_bucket_width": price_step,
            "bin_size_bps": bin_size_bps,
            "value_area_pct": value_area_pct,
            "poc": {
                "price_low": reference_price + poc_index * price_step,
                "price_high": reference_price + (poc_index + 1) * price_step,
                "price_mid": reference_price + (poc_index + 0.5) * price_step,
                "volume_notional_proxy": buckets[poc_index]["buy_notional"] + buckets[poc_index]["sell_notional"],
            },
            "value_area": {
                "val": reference_price + low_idx * price_step,
                "vah": reference_price + (high_idx + 1) * price_step,
                "included_notional_proxy": accumulated,
                "observed_total_notional_proxy": total_profile_notional,
                "achieved_value_area_pct": accumulated / total_profile_notional * 100 if total_profile_notional else None,
            },
            "buckets": profile_rows,
        },
        "price_cvd_divergence": {
            "classification": divergence,
            "price_change_pct": price_change_pct,
            "net_cvd_quantity": net_cvd_qty,
            "interpretation": "Candidate only; aggregate trade flow does not identify participant intent or predict price.",
        },
        "cvd_series": cvd_points[-500:],
        "coverage": {
            "requested_start_time_ms": start_time_ms,
            "requested_end_time_ms": end_time_ms,
            "first_observed_trade_time_ms": valid[0]["trade_time_ms"],
            "last_observed_trade_time_ms": valid[-1]["trade_time_ms"],
            "starts_at_requested_boundary": valid[0]["trade_time_ms"] <= start_time_ms + 1000,
            "ends_near_requested_boundary": valid[-1]["trade_time_ms"] >= end_time_ms - 60000,
            "returned_trade_count": len(valid),
        },
        "warnings": [
            "Only locally collected aggregate trades are analyzed; no pre-collection backfill is available.",
            "A capped or interrupted collector can leave unobserved trades; observed totals are not guaranteed exchange-wide totals.",
            "CVD is reset at the requested window start and is not a standalone directional signal.",
            "POC, VAH and VAL are calculated from trade notional proxies in configurable price buckets, not exchange-native volume-profile levels.",
            "For COIN_M, price multiplied by contract quantity is a raw proxy; contract face value is not applied.",
            "Aggregate trades do not identify individual traders, institutional participants, order intent, or hidden liquidity.",
        ],
    }
