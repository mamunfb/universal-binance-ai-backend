from __future__ import annotations

import math
from typing import Any


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _nearest(
    rows: list[dict[str, Any]], timestamp: int, key: str, max_lag_ms: int,
    direction: str | None = None,
) -> dict[str, Any] | None:
    candidates = []
    for row in rows:
        value = row.get(key)
        try:
            value = int(value)
        except (TypeError, ValueError, OverflowError):
            continue
        if direction == "before" and value > timestamp:
            continue
        if direction == "after" and value < timestamp:
            continue
        lag = abs(value - timestamp)
        if lag <= max_lag_ms:
            candidates.append((lag, row))
    return min(candidates, key=lambda item: item[0])[1] if candidates else None


def _pivot_levels(candles: list[dict[str, Any]], left: int, right: int) -> tuple[list[dict], list[dict]]:
    highs, lows = [], []
    for i in range(left, len(candles) - right):
        high, low = _finite(candles[i].get("high")), _finite(candles[i].get("low"))
        if high is None or low is None:
            continue
        neighbours = candles[i-left:i] + candles[i+1:i+right+1]
        nh = [_finite(item.get("high")) for item in neighbours]
        nl = [_finite(item.get("low")) for item in neighbours]
        if all(value is not None and high > value for value in nh):
            highs.append({"index": i, "time_ms": candles[i]["open_time_ms"], "price": high})
        if all(value is not None and low < value for value in nl):
            lows.append({"index": i, "time_ms": candles[i]["open_time_ms"], "price": low})
    return highs, lows


def _equal_zones(levels: list[dict], tolerance_bps: float, side: str) -> list[dict]:
    zones = []
    for i, first in enumerate(levels):
        matches = [first]
        for other in levels[i + 1:]:
            distance = abs(other["price"] - first["price"]) / first["price"] * 10000
            if distance <= tolerance_bps:
                matches.append(other)
        if len(matches) >= 2:
            prices = [item["price"] for item in matches]
            zones.append({
                "side": side, "level": sum(prices) / len(prices),
                "touch_count": len(matches),
                "first_pivot_time_ms": min(item["time_ms"] for item in matches),
                "last_pivot_time_ms": max(item["time_ms"] for item in matches),
                "tolerance_bps": tolerance_bps,
            })
    # Deduplicate overlapping clusters by keeping the most populated representative.
    unique = {}
    for zone in zones:
        key = round(zone["level"], 8)
        if key not in unique or zone["touch_count"] > unique[key]["touch_count"]:
            unique[key] = zone
    return sorted(unique.values(), key=lambda item: item["last_pivot_time_ms"], reverse=True)[:10]


def _depth_notional(sample: dict[str, Any] | None, side: str) -> float | None:
    if sample is None:
        return None
    levels = sample.get(side)
    if not isinstance(levels, list):
        return None
    total = 0.0
    for level in levels:
        if not isinstance(level, (list, tuple)) or len(level) < 2:
            continue
        price, quantity = _finite(level[0]), _finite(level[1])
        if price is None or quantity is None or price <= 0 or quantity < 0:
            continue
        total += price * quantity
    return total


def analyze_liquidity_sweep_confirmation(
    candles: list[dict[str, Any]], trades: list[dict[str, Any]],
    order_book_samples: list[dict[str, Any]], market: str, symbol: str,
    open_interest_records: list[dict[str, Any]] | None = None,
    funding_events: list[dict[str, Any]] | None = None,
    swing_left: int = 2, swing_right: int = 2,
    equal_level_tolerance_bps: float = 8.0,
    trade_window_ms: int = 5 * 60_000,
    order_book_max_lag_ms: int = 120_000,
    derivatives_max_lag_ms: int = 60 * 60_000,
) -> dict[str, Any]:
    """Correlate OHLC sweep candidates with nearby locally captured public market data."""
    if not 1 <= swing_left <= 10 or not 1 <= swing_right <= 10:
        raise ValueError("swing_left and swing_right must be between 1 and 10")
    if not 0.1 <= equal_level_tolerance_bps <= 100:
        raise ValueError("equal_level_tolerance_bps must be between 0.1 and 100")
    if not 1 <= len(candles) <= 1000:
        raise ValueError("candles must contain between 1 and 1000 rows")
    normalized_market, normalized_symbol = market.upper(), symbol.upper()
    if normalized_market not in {"SPOT", "USD_M", "COIN_M"} or not normalized_symbol:
        raise ValueError("Invalid market or symbol")

    required = max(10, swing_left + swing_right + 3)
    if len(candles) < required:
        return {
            "status": "INSUFFICIENT_CANDLE_DATA", "market": normalized_market,
            "symbol": normalized_symbol, "available_candles": len(candles),
            "required_candles": required, "sweep_candidates": [],
            "confirmation_status": "INSUFFICIENT_DATA",
        }

    ordered = sorted(candles, key=lambda row: int(row["open_time_ms"]))
    for row in ordered:
        values = [_finite(row.get(key)) for key in ("open", "high", "low", "close")]
        if any(value is None or value <= 0 for value in values):
            raise ValueError("Candle OHLC values must be finite and positive")
        open_, high, low, close = values
        if high < max(open_, close, low) or low > min(open_, close, high):
            raise ValueError("Inconsistent candle OHLC values")

    highs, lows = _pivot_levels(ordered, swing_left, swing_right)
    equal_highs = _equal_zones(highs, equal_level_tolerance_bps, "BUY_SIDE")
    equal_lows = _equal_zones(lows, equal_level_tolerance_bps, "SELL_SIDE")
    candidates = []
    scan_start = max(0, len(ordered) - 30)
    for pivot in highs:
        if pivot["index"] < scan_start or pivot["index"] >= len(ordered) - 1:
            continue
        for index in range(pivot["index"] + 1, len(ordered)):
            row = ordered[index]
            if float(row["high"]) > pivot["price"] and float(row["close"]) < pivot["price"]:
                candidates.append({
                    "direction": "BEARISH_AFTER_BUY_SIDE_SWEEP",
                    "sweep_type": "BUY_SIDE_LIQUIDITY_SWEEP_CANDIDATE",
                    "level": pivot["price"], "wick_extreme": float(row["high"]),
                    "reclaim_close": float(row["close"]),
                    "pivot_time_ms": pivot["time_ms"],
                    "sweep_time_ms": int(row["open_time_ms"]),
                    "candle_index": index,
                })
                break
    for pivot in lows:
        if pivot["index"] < scan_start or pivot["index"] >= len(ordered) - 1:
            continue
        for index in range(pivot["index"] + 1, len(ordered)):
            row = ordered[index]
            if float(row["low"]) < pivot["price"] and float(row["close"]) > pivot["price"]:
                candidates.append({
                    "direction": "BULLISH_AFTER_SELL_SIDE_SWEEP",
                    "sweep_type": "SELL_SIDE_LIQUIDITY_SWEEP_CANDIDATE",
                    "level": pivot["price"], "wick_extreme": float(row["low"]),
                    "reclaim_close": float(row["close"]),
                    "pivot_time_ms": pivot["time_ms"],
                    "sweep_time_ms": int(row["open_time_ms"]),
                    "candle_index": index,
                })
                break
    candidates.sort(key=lambda item: item["sweep_time_ms"], reverse=True)

    enriched = []
    for candidate in candidates[:10]:
        timestamp = candidate["sweep_time_ms"]
        end = timestamp + trade_window_ms
        interval_trades = []
        for trade in trades:
            try:
                trade_time = int(trade.get("trade_time_ms", -1))
            except (TypeError, ValueError, OverflowError):
                continue
            if timestamp <= trade_time <= end:
                interval_trades.append(trade)
        buy_qty = sell_qty = 0.0
        for trade in interval_trades:
            quantity = _finite(trade.get("quantity"))
            if quantity is None or quantity <= 0:
                continue
            side = str(trade.get("aggressor_side", "")).upper()
            if side == "BUY":
                buy_qty += quantity
            elif side == "SELL":
                sell_qty += quantity
        net_qty = buy_qty - sell_qty
        expected = "BUY" if candidate["direction"].startswith("BULLISH") else "SELL"
        trade_confirmation = (
            "ALIGNED_AGGRESSOR_FLOW" if interval_trades and net_qty > 0 and expected == "BUY"
            or interval_trades and net_qty < 0 and expected == "SELL"
            else "OPPOSING_AGGRESSOR_FLOW" if interval_trades and net_qty != 0
            else "FLAT_OR_INSUFFICIENT_TRADE_FLOW"
        )

        before = _nearest(order_book_samples, timestamp, "event_time_ms", order_book_max_lag_ms, "before")
        after = _nearest(order_book_samples, end, "event_time_ms", order_book_max_lag_ms, "after")
        before_bid, after_bid = _depth_notional(before, "bids"), _depth_notional(after, "bids")
        before_ask, after_ask = _depth_notional(before, "asks"), _depth_notional(after, "asks")
        if None not in (before_bid, after_bid, before_ask, after_ask):
            bid_change_pct = ((after_bid - before_bid) / before_bid * 100) if before_bid else None
            ask_change_pct = ((after_ask - before_ask) / before_ask * 100) if before_ask else None
            book_status = (
                "SAMPLED_DEPTH_CHANGED"
                if (bid_change_pct is not None and abs(bid_change_pct) >= 0.01)
                or (ask_change_pct is not None and abs(ask_change_pct) >= 0.01)
                else "PAIRED_SAMPLES_NO_MATERIAL_CHANGE"
            )
        else:
            bid_change_pct = ask_change_pct = None
            book_status = "NO_NEARBY_PAIRED_SAMPLES"

        oi = _nearest(open_interest_records or [], timestamp, "timestamp_ms", derivatives_max_lag_ms)
        funding = _nearest(funding_events or [], timestamp, "funding_time_ms", derivatives_max_lag_ms)
        oi_context = None if oi is None else {
            "timestamp_ms": oi["timestamp_ms"],
            "sum_open_interest": oi.get("sum_open_interest"),
            "sum_open_interest_value": oi.get("sum_open_interest_value"),
            "alignment_lag_ms": abs(int(oi["timestamp_ms"]) - timestamp),
        }
        funding_context = None if funding is None else {
            "funding_time_ms": funding["funding_time_ms"],
            "funding_rate": funding.get("funding_rate"),
            "alignment_lag_ms": abs(int(funding["funding_time_ms"]) - timestamp),
        }
        equal_side = "BUY_SIDE" if expected == "SELL" else "SELL_SIDE"
        relevant_zones = equal_highs if equal_side == "BUY_SIDE" else equal_lows
        nearest_zone = min(relevant_zones, key=lambda z: abs(z["level"] - candidate["level"])) if relevant_zones else None
        candidate["equal_level_zone"] = nearest_zone
        candidate["aggressor_flow"] = {
            "trade_count": len(interval_trades), "buy_quantity": buy_qty,
            "sell_quantity": sell_qty, "net_cvd_quantity": net_qty,
            "confirmation": trade_confirmation, "window_end_time_ms": end,
        }
        candidate["order_book_context"] = {
            "status": book_status, "before_event_time_ms": before.get("event_time_ms") if before else None,
            "after_event_time_ms": after.get("event_time_ms") if after else None,
            "max_sample_lag_ms": order_book_max_lag_ms,
            "bid_depth_change_pct": bid_change_pct, "ask_depth_change_pct": ask_change_pct,
        }
        candidate["derivatives_context"] = {
            "open_interest": oi_context, "funding": funding_context,
            "alignment_policy": "Nearest observation only within configured lag; no forward-fill or interpolation.",
        }
        evidence = [trade_confirmation == "ALIGNED_AGGRESSOR_FLOW",
                    book_status == "SAMPLED_DEPTH_CHANGED"]
        candidate["evidence_count"] = sum(evidence)
        candidate["confirmation_status"] = (
            "MULTI_SOURCE_CANDIDATE" if sum(evidence) == 2
            else "SINGLE_SOURCE_CANDIDATE" if sum(evidence) == 1
            else "OHLC_ONLY_CANDIDATE"
        )
        enriched.append(candidate)

    return {
        "status": "COMPLETED" if enriched else "NO_RECENT_SWEEP_CANDIDATE",
        "market": normalized_market, "symbol": normalized_symbol,
        "candle_count": len(ordered),
        "latest_candle_open_time_ms": ordered[-1]["open_time_ms"],
        "swing_settings": {"left": swing_left, "right": swing_right},
        "equal_level_zones": {"buy_side": equal_highs, "sell_side": equal_lows},
        "sweep_candidates": enriched,
        "data_quality": {
            "candle_count": len(ordered), "aggregate_trade_rows": len(trades),
            "order_book_sample_count": len(order_book_samples),
            "open_interest_record_count": len(open_interest_records or []),
            "funding_event_count": len(funding_events or []),
            "derivatives_context_supported_for": "USD_M only",
            "order_book_pairing_max_lag_ms": order_book_max_lag_ms,
            "trade_confirmation_window_ms": trade_window_ms,
        },
        "limitations": [
            "A wick beyond a prior swing followed by a close back inside is an OHLC sweep candidate, not proof that stop orders were triggered.",
            "Equal-high/equal-low zones are tolerance-based swing clusters, not observed resting stop orders.",
            "Aggregate trades are locally captured and may be incomplete; aggressor flow does not identify participants.",
            "Order-book depth is sampled and paired only when both samples fall within the explicit lag; changes do not prove spoofing or intent.",
            "Open interest and funding are nearest timestamp context only, not directional confirmation; no interpolation or forward-fill is used.",
            "Funding events are sparse and may not align with the sweep timestamp; null means no observation inside the allowed lag.",
            "No probability, trading entry, stop, target, liquidation trigger, or investment recommendation is produced.",
        ],
    }
