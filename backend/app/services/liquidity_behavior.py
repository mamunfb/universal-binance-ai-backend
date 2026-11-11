from __future__ import annotations

import math
from collections import defaultdict
from typing import Any


def _integer(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _finite(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _levels(rows: list[Any], side: str) -> dict[float, float]:
    result: dict[float, float] = {}
    if not isinstance(rows, list):
        return result
    for item in rows:
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue
        price, quantity = _finite(item[0]), _finite(item[1])
        if price is not None and quantity is not None and price > 0 and quantity > 0:
            result[price] = quantity
    return result


def analyze_liquidity_behavior(
    snapshots: list[dict[str, Any]], trades: list[dict[str, Any]],
    market: str, symbol: str, min_removed_notional: float = 10000.0,
    min_aggressive_notional: float = 10000.0, max_absorption_move_bps: float = 2.0,
    trade_price_band_bps: float = 2.0,
) -> dict[str, Any]:
    market, symbol = market.upper(), symbol.upper()
    if market not in {"SPOT", "USD_M", "COIN_M"}:
        raise ValueError("Unsupported market")
    if not symbol or len(symbol) > 40:
        raise ValueError("Invalid symbol")
    for name, value, maximum in (
        ("min_removed_notional", min_removed_notional, 1e15),
        ("min_aggressive_notional", min_aggressive_notional, 1e15),
        ("max_absorption_move_bps", max_absorption_move_bps, 1000),
        ("trade_price_band_bps", trade_price_band_bps, 1000),
    ):
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value) or value < 0 or value > maximum):
            raise ValueError(f"{name} is outside its allowed range")
    valid_snapshots = []
    rejected_snapshots = 0
    for row in snapshots:
        if not isinstance(row, dict):
            rejected_snapshots += 1
            continue
        stamp = _integer(row.get("event_time_ms"))
        update_id = _integer(row.get("update_id", 0))
        mid_price = _finite(row.get("mid_price"))
        if stamp is None or update_id is None or mid_price is None or mid_price <= 0:
            rejected_snapshots += 1
            continue
        valid_snapshots.append(row)
    valid_trades = []
    rejected_trades = 0
    for row in trades:
        if not isinstance(row, dict):
            rejected_trades += 1
            continue
        stamp = _integer(row.get("trade_time_ms"))
        notional = _finite(row.get("notional"))
        price = _finite(row.get("price"))
        side = str(row.get("aggressor_side", "")).upper()
        if stamp is None or notional is None or notional < 0 or price is None or price <= 0 or side not in {"BUY", "SELL"}:
            rejected_trades += 1
            continue
        valid_trades.append(row)
    ordered = sorted(valid_snapshots, key=lambda row: (row["event_time_ms"], row.get("update_id", 0)))
    ordered_trades = sorted(valid_trades, key=lambda row: row["trade_time_ms"])
    base = {
        "market": market, "symbol": symbol,
        "snapshot_count": len(ordered), "rejected_snapshot_count": rejected_snapshots,
        "trade_count": len(ordered_trades), "rejected_trade_count": rejected_trades,
        "status": "INSUFFICIENT_DATA",
        "method": "Adjacent sampled depth snapshots plus aggregate taker-trade flow",
    }
    if len(ordered) < 2:
        return {**base, "reason": "AT_LEAST_TWO_DEPTH_SAMPLES_REQUIRED"}
    previous, latest = ordered[-2], ordered[-1]
    start_ms = previous["event_time_ms"]
    end_ms = latest["event_time_ms"]
    if end_ms <= start_ms:
        return {**base, "reason": "NON_INCREASING_SNAPSHOT_TIMESTAMPS"}
    interval_trades = [
        row for row in ordered_trades
        if start_ms < row["trade_time_ms"] <= end_ms
    ]
    buy_notional = sum(row["notional"] for row in interval_trades if row.get("aggressor_side") == "BUY")
    sell_notional = sum(row["notional"] for row in interval_trades if row.get("aggressor_side") == "SELL")
    total_trade_notional = buy_notional + sell_notional
    flow_imbalance = (buy_notional - sell_notional) / total_trade_notional if total_trade_notional else None

    old_bids, old_asks = _levels(previous.get("bids", []), "BID"), _levels(previous.get("asks", []), "ASK")
    new_bids, new_asks = _levels(latest.get("bids", []), "BID"), _levels(latest.get("asks", []), "ASK")
    old_mid, new_mid = _finite(previous["mid_price"]), _finite(latest["mid_price"])
    if old_mid is None or new_mid is None or old_mid <= 0 or new_mid <= 0:
        return {**base, "reason": "INVALID_MID_PRICE"}
    mid_move_bps = (new_mid - old_mid) / old_mid * 10000 if old_mid else None

    trade_by_side = defaultdict(float)
    for row in interval_trades:
        price = _finite(row.get("price"))
        notional = _finite(row.get("notional"))
        if price is None or notional is None or price <= 0 or notional < 0:
            continue
        side = str(row.get("aggressor_side", "")).upper()
        if side in {"BUY", "SELL"}:
            trade_by_side[(side, price)] += notional

    pull_candidates = []
    for side, old_book, new_book in (("BID", old_bids, new_bids), ("ASK", old_asks, new_asks)):
        for price, old_qty in old_book.items():
            new_qty = new_book.get(price, 0.0)
            removed_qty = max(0.0, old_qty - new_qty)
            removed_value = removed_qty * price
            if removed_value < min_removed_notional:
                continue
            aggressor = "SELL" if side == "BID" else "BUY"
            traded_near_level = sum(
                value for (trade_side, trade_price), value in trade_by_side.items()
                if trade_side == aggressor and abs(trade_price - price) / price * 10000 <= trade_price_band_bps
            )
            classification = (
                "PULLING_CANDIDATE_LOW_MATCHED_TRADE_FLOW"
                if traded_near_level < removed_value * 0.25
                else "TRADE_CONSUMPTION_OR_MIXED"
            )
            pull_candidates.append({
                "book_side": side, "price": price, "previous_quantity": old_qty,
                "current_quantity": new_qty, "removed_quantity": removed_qty,
                "removed_value_proxy": removed_value,
                "matched_aggressive_trade_value_proxy": traded_near_level,
                "classification": classification,
            })
    pull_candidates.sort(key=lambda row: row["removed_value_proxy"], reverse=True)

    old_bid_value = sum(p * q for p, q in old_bids.items())
    old_ask_value = sum(p * q for p, q in old_asks.items())
    new_bid_value = sum(p * q for p, q in new_bids.items())
    new_ask_value = sum(p * q for p, q in new_asks.items())
    absorption = []
    if abs(mid_move_bps or 0) <= max_absorption_move_bps:
        if buy_notional >= min_aggressive_notional and new_ask_value >= old_ask_value * 0.8:
            absorption.append({
                "aggressor_side": "BUY", "resting_side": "ASK",
                "aggressive_trade_value_proxy": buy_notional,
                "resting_depth_before_proxy": old_ask_value,
                "resting_depth_after_proxy": new_ask_value,
                "classification": "BUY_PRESSURE_WITH_STABLE_ASK_DEPTH_CANDIDATE",
            })
        if sell_notional >= min_aggressive_notional and new_bid_value >= old_bid_value * 0.8:
            absorption.append({
                "aggressor_side": "SELL", "resting_side": "BID",
                "aggressive_trade_value_proxy": sell_notional,
                "resting_depth_before_proxy": old_bid_value,
                "resting_depth_after_proxy": new_bid_value,
                "classification": "SELL_PRESSURE_WITH_STABLE_BID_DEPTH_CANDIDATE",
            })

    return {
        **base, "status": "COMPLETED",
        "interval": {"start_time_ms": start_ms, "end_time_ms": end_ms,
                     "duration_ms": end_ms - start_ms, "mid_price_move_bps": mid_move_bps},
        "aggressive_trade_flow": {
            "buy_notional_proxy": buy_notional, "sell_notional_proxy": sell_notional,
            "total_notional_proxy": total_trade_notional,
            "buy_sell_imbalance": flow_imbalance,
            "trade_count": len(interval_trades),
        },
        "liquidity_change": {
            "bid_value_before_proxy": old_bid_value, "bid_value_after_proxy": new_bid_value,
            "ask_value_before_proxy": old_ask_value, "ask_value_after_proxy": new_ask_value,
            "bid_change_pct": (new_bid_value - old_bid_value) / old_bid_value * 100 if old_bid_value else None,
            "ask_change_pct": (new_ask_value - old_ask_value) / old_ask_value * 100 if old_ask_value else None,
        },
        "liquidity_withdrawal_candidates": pull_candidates[:100],
        "absorption_candidates": absorption,
        "thresholds": {
            "min_removed_notional_proxy": min_removed_notional,
            "min_aggressive_notional_proxy": min_aggressive_notional,
            "max_absorption_move_bps": max_absorption_move_bps,
            "trade_price_band_bps": trade_price_band_bps,
        },
        "warnings": [
            "These are heuristic candidates from two sampled snapshots, not proof of spoofing, manipulation, or deliberate absorption.",
            "Orders can be added, cancelled, repriced, or executed between samples; intermediate events may be missed.",
            "AggTrade is aggregated public market trade data, not every exchange event or participant identity.",
            "Trade matching uses a configurable price band and is approximate, not exact order-level attribution.",
            "For COIN_M, price multiplied by contract quantity is only a raw proxy; contract-specific face value is not applied.",
            "Absorption candidate requires aggressive trade flow, limited midpoint movement, and retained same-side displayed depth; it is not a verified institutional signal.",
            "Data coverage depends on both collectors being enabled and synchronized; no pre-deployment backfill is performed.",
        ],
    }
