from __future__ import annotations

import math
from datetime import datetime, timezone
from statistics import median
from typing import Any


def _number(value: Any) -> float | None:
    try:
        if isinstance(value, bool):
            return None
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError, OverflowError):
        return None


def analyze_order_book(
    book: dict[str, Any], market: str, symbol: str,
    levels: int = 100, wall_multiplier: float = 3.0,
) -> dict[str, Any]:
    if market not in {"SPOT", "USD_M", "COIN_M"}:
        raise ValueError("Unsupported market")
    symbol = symbol.strip().upper()
    if not symbol or len(symbol) > 40:
        raise ValueError("Invalid symbol")
    if not 1 <= levels <= 1000:
        raise ValueError("levels must be between 1 and 1000")
    if not math.isfinite(wall_multiplier) or not 1 <= wall_multiplier <= 20:
        raise ValueError("wall_multiplier must be between 1 and 20")

    parsed: dict[str, list[dict[str, float]]] = {}
    rejected = {"bids": 0, "asks": 0}
    for side in ("bids", "asks"):
        raw = book.get(side)
        if not isinstance(raw, list):
            raw = []
        rows: list[dict[str, float]] = []
        for item in raw[:levels]:
            if not isinstance(item, (list, tuple)) or len(item) < 2:
                rejected[side] += 1
                continue
            price, quantity = _number(item[0]), _number(item[1])
            if price is None or quantity is None or price <= 0 or quantity <= 0:
                rejected[side] += 1
                continue
            rows.append({"price": price, "quantity": quantity, "notional": price * quantity})
        parsed[side] = rows

    bids, asks = parsed["bids"], parsed["asks"]
    base = {
        "status": "INCOMPLETE", "market": market, "symbol": symbol,
        "levels_requested": levels, "bid_levels_received": len(bids),
        "ask_levels_received": len(asks), "rejected_rows": rejected,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "Binance public REST order-book snapshot",
    }
    if not bids or not asks:
        return {**base, "reason": "MISSING_VALID_BID_OR_ASK_LEVELS"}
    # Binance returns bids descending and asks ascending. Sort defensively.
    bids.sort(key=lambda row: row["price"], reverse=True)
    asks.sort(key=lambda row: row["price"])
    best_bid, best_ask = bids[0]["price"], asks[0]["price"]
    if best_bid >= best_ask:
        return {**base, "best_bid": best_bid, "best_ask": best_ask,
                "reason": "CROSSED_OR_LOCKED_BOOK"}

    mid = (best_bid + best_ask) / 2
    spread = best_ask - best_bid
    bid_notional = sum(row["notional"] for row in bids)
    ask_notional = sum(row["notional"] for row in asks)
    total = bid_notional + ask_notional
    bid_qty, ask_qty = bids[0]["quantity"], asks[0]["quantity"]
    microprice = (
        best_ask * bid_qty + best_bid * ask_qty
    ) / (bid_qty + ask_qty) if bid_qty + ask_qty else None
    bid_median = median(row["notional"] for row in bids)
    ask_median = median(row["notional"] for row in asks)
    walls = []
    for side, rows, baseline in (("BID", bids, bid_median), ("ASK", asks, ask_median)):
        for row in rows:
            multiple = row["notional"] / baseline if baseline > 0 else None
            if multiple is not None and multiple >= wall_multiplier:
                walls.append({
                    "side": side, "price": row["price"],
                    "quantity": row["quantity"], "notional": row["notional"],
                    "multiple_of_side_median_notional": multiple,
                    "distance_from_mid_bps": (row["price"] - mid) / mid * 10000,
                })
    walls.sort(key=lambda row: row["notional"], reverse=True)

    bands = {}
    for band_bps in (5, 10, 25, 50, 100):
        lower, upper = mid * (1 - band_bps / 10000), mid * (1 + band_bps / 10000)
        bid_band = sum(row["notional"] for row in bids if row["price"] >= lower)
        ask_band = sum(row["notional"] for row in asks if row["price"] <= upper)
        denom = bid_band + ask_band
        bands[str(band_bps)] = {
            "bid_notional": bid_band, "ask_notional": ask_band,
            "imbalance": (bid_band - ask_band) / denom if denom else None,
        }

    cumulative = {"bids": [], "asks": []}
    for side, rows in (("bids", bids), ("asks", asks)):
        running = 0.0
        for row in rows:
            running += row["notional"]
            cumulative[side].append({
                "price": row["price"], "level_notional": row["notional"],
                "cumulative_notional": running,
            })

    return {
        **base, "status": "COMPLETED",
        "snapshot": {
            "last_update_id": book.get("lastUpdateId"),
            "event_time_ms": book.get("E"), "transaction_time_ms": book.get("T"),
        },
        "best_bid": best_bid, "best_ask": best_ask, "mid_price": mid,
        "spread": spread, "spread_bps": spread / mid * 10000,
        "microprice": microprice,
        "microprice_deviation_bps": (microprice - mid) / mid * 10000 if microprice is not None else None,
        "depth": {
            "bid_notional": bid_notional, "ask_notional": ask_notional,
            "total_notional": total,
            "imbalance": (bid_notional - ask_notional) / total if total else None,
            "bid_quantity": sum(row["quantity"] for row in bids),
            "ask_quantity": sum(row["quantity"] for row in asks),
        },
        "near_mid_depth_bands_bps": bands,
        "large_visible_order_candidates": walls[:50],
        "wall_method": {
            "threshold": f"Each level notional >= {wall_multiplier}x median notional on its own side.",
            "bid_side_median_notional": bid_median,
            "ask_side_median_notional": ask_median,
            "warning": "Relative visible-size heuristic only; not proof of spoofing, intent, or support/resistance.",
        },
        "cumulative_depth": cumulative,
        "interpretation_warnings": [
            "This is a single REST snapshot, not a synchronized real-time order-book stream.",
            "Visible limit orders can be modified or cancelled; walls are not guaranteed liquidity.",
            "Displayed depth omits hidden liquidity and does not reveal participant identity or intent.",
            "Imbalance and microprice are descriptive pressure proxies, not reliable price predictions.",
            "No historical liquidity tracking is performed by this endpoint.",
        ],
    }
