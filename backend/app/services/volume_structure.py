from datetime import datetime, timezone
from typing import Any


def _ohlcv(candles: list[list[Any]]) -> tuple[list[float], list[float], list[float], list[float], list[float]]:
    if not candles:
        raise ValueError("at least one candle is required")
    highs = [float(row[2]) for row in candles]
    lows = [float(row[3]) for row in candles]
    closes = [float(row[4]) for row in candles]
    volumes = [float(row[5]) for row in candles]
    opens = [float(row[1]) for row in candles]
    if any(v <= 0 for v in highs + lows + closes + opens) or any(v < 0 for v in volumes):
        raise ValueError("OHLC prices must be positive and volume cannot be negative")
    return opens, highs, lows, closes, volumes


def calculate_vwap(candles: list[list[Any]], anchor_index: int = 0) -> dict[str, Any]:
    _, highs, lows, closes, volumes = _ohlcv(candles)
    if anchor_index < 0 or anchor_index >= len(candles):
        raise ValueError("anchor_index must reference a candle in the input")
    numerator = 0.0
    denominator = 0.0
    series: list[dict[str, float | int]] = []
    for index in range(anchor_index, len(candles)):
        typical_price = (highs[index] + lows[index] + closes[index]) / 3.0
        numerator += typical_price * volumes[index]
        denominator += volumes[index]
        series.append({
            "candle_index": index,
            "vwap": numerator / denominator if denominator else None,
            "cumulative_volume": denominator,
        })
    return {
        "status": "COMPLETED" if denominator > 0 else "INCOMPLETE",
        "method": "Cumulative typical-price VWAP from selected anchor candle",
        "anchor_index": anchor_index,
        "latest_vwap": series[-1]["vwap"] if series else None,
        "latest_close": closes[-1],
        "series": series,
        "warning": "This is anchored to the supplied candle window. A true exchange session VWAP requires a correctly defined session boundary and timezone.",
    }


def calculate_volume_profile(
    candles: list[list[Any]], bins: int = 48, value_area_pct: float = 0.70
) -> dict[str, Any]:
    _, highs, lows, closes, volumes = _ohlcv(candles)
    if bins < 5 or bins > 200:
        raise ValueError("bins must be between 5 and 200")
    if not 0.5 <= value_area_pct <= 0.95:
        raise ValueError("value_area_pct must be between 0.5 and 0.95")
    low_price, high_price = min(lows), max(highs)
    if high_price <= low_price:
        return {"status": "INCOMPLETE", "reason": "Price range is too narrow to build a profile"}
    width = (high_price - low_price) / bins
    profile = [0.0] * bins
    for low, high, close, volume in zip(lows, highs, closes, volumes):
        typical = (high + low + close) / 3.0
        index = min(bins - 1, max(0, int((typical - low_price) / width)))
        profile[index] += volume
    total_volume = sum(profile)
    if total_volume <= 0:
        return {"status": "INCOMPLETE", "reason": "No positive traded volume in input candles"}
    poc_index = max(range(bins), key=lambda i: profile[i])
    left = right = poc_index
    accumulated = profile[poc_index]
    target = total_volume * value_area_pct
    while accumulated < target and (left > 0 or right < bins - 1):
        left_volume = profile[left - 1] if left > 0 else -1.0
        right_volume = profile[right + 1] if right < bins - 1 else -1.0
        if right_volume > left_volume:
            right += 1
            accumulated += profile[right]
        else:
            left -= 1
            accumulated += profile[left]
    rows = []
    for index, volume in enumerate(profile):
        rows.append({
            "bin": index,
            "price_low": low_price + width * index,
            "price_high": low_price + width * (index + 1),
            "price_mid": low_price + width * (index + 0.5),
            "volume": volume,
            "volume_share": volume / total_volume,
            "node": "POC" if index == poc_index else (
                "VALUE_AREA" if left <= index <= right else "OUTSIDE_VALUE_AREA"
            ),
        })
    return {
        "status": "COMPLETED",
        "method": "OHLCV typical-price volume allocation into fixed price bins",
        "bin_count": bins,
        "value_area_pct_target": value_area_pct,
        "total_allocated_volume": total_volume,
        "poc": rows[poc_index],
        "vah": rows[right]["price_high"],
        "val": rows[left]["price_low"],
        "profile": rows,
        "warning": "This is an approximation: candle volume is assigned to one typical-price bin. It is not trade-level volume-at-price data and does not identify true bid/ask volume.",
    }


def _pivots(values: list[float], left: int, right: int, kind: str) -> list[tuple[int, float]]:
    result = []
    for i in range(left, len(values) - right):
        window = values[i - left:i + right + 1]
        if kind == "high" and values[i] == max(window) and window.count(values[i]) == 1:
            result.append((i, values[i]))
        if kind == "low" and values[i] == min(window) and window.count(values[i]) == 1:
            result.append((i, values[i]))
    return result


def analyze_market_structure(
    candles: list[list[Any]], pivot_left: int = 3, pivot_right: int = 3
) -> dict[str, Any]:
    _, highs, lows, closes, _ = _ohlcv(candles)
    if pivot_left < 1 or pivot_right < 1:
        raise ValueError("pivot_left and pivot_right must be at least 1")
    swing_highs = _pivots(highs, pivot_left, pivot_right, "high")
    swing_lows = _pivots(lows, pivot_left, pivot_right, "low")
    if not swing_highs or not swing_lows:
        return {"status": "INCOMPLETE", "reason": "Not enough confirmed swing highs and lows"}
    events: list[dict[str, Any]] = []
    trend = "UNCONFIRMED"
    broken_highs: set[int] = set()
    broken_lows: set[int] = set()
    for index, close in enumerate(closes):
        eligible_highs = [(i, p) for i, p in swing_highs if i + pivot_right < index and i not in broken_highs]
        eligible_lows = [(i, p) for i, p in swing_lows if i + pivot_right < index and i not in broken_lows]
        if eligible_highs:
            pivot_index, level = eligible_highs[-1]
            if close > level:
                event_type = "BOS" if trend in ("BULLISH", "UNCONFIRMED") else "CHOCH"
                events.append({"type": event_type, "direction": "BULLISH", "candle_index": index,
                               "broken_pivot_index": pivot_index, "level": level, "close": close})
                trend = "BULLISH"
                broken_highs.add(pivot_index)
        if eligible_lows:
            pivot_index, level = eligible_lows[-1]
            if close < level:
                event_type = "BOS" if trend in ("BEARISH", "UNCONFIRMED") else "CHOCH"
                events.append({"type": event_type, "direction": "BEARISH", "candle_index": index,
                               "broken_pivot_index": pivot_index, "level": level, "close": close})
                trend = "BEARISH"
                broken_lows.add(pivot_index)
    # Sweep candidates: wick crosses a confirmed level but closes back on the original side.
    sweeps = []
    for pivot_index, level in swing_highs:
        for index in range(pivot_index + pivot_right + 1, len(candles)):
            if highs[index] > level and closes[index] < level:
                sweeps.append({"type": "BUY_SIDE_LIQUIDITY_SWEEP", "candle_index": index,
                               "level": level, "pivot_index": pivot_index})
                break
    for pivot_index, level in swing_lows:
        for index in range(pivot_index + pivot_right + 1, len(candles)):
            if lows[index] < level and closes[index] > level:
                sweeps.append({"type": "SELL_SIDE_LIQUIDITY_SWEEP", "candle_index": index,
                               "level": level, "pivot_index": pivot_index})
                break
    return {
        "status": "COMPLETED",
        "method": "Confirmed symmetric pivots and close-based level breaks",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "latest_close": closes[-1],
        "latest_confirmed_swing_high": {"index": swing_highs[-1][0], "price": swing_highs[-1][1]},
        "latest_confirmed_swing_low": {"index": swing_lows[-1][0], "price": swing_lows[-1][1]},
        "trend_state": trend,
        "events": events,
        "liquidity_sweep_candidates": sweeps,
        "warning": "BOS/CHoCH and sweep labels are rule-based approximations, not universal definitions or proof of institutional activity. Pivots require right-side candles to confirm.",
    }
