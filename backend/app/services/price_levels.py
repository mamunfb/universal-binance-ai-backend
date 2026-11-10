from datetime import datetime, timezone
from typing import Any


def _pivot_indices(values: list[float], left: int, right: int, kind: str) -> list[int]:
    indices: list[int] = []
    for index in range(left, len(values) - right):
        window = values[index - left:index + right + 1]
        current = values[index]
        if kind == "high" and current == max(window) and window.count(current) == 1:
            indices.append(index)
        elif kind == "low" and current == min(window) and window.count(current) == 1:
            indices.append(index)
    return indices


def _cluster_levels(points: list[tuple[float, int]], tolerance_pct: float) -> list[dict[str, Any]]:
    clusters: list[dict[str, Any]] = []
    for price, index in sorted(points):
        match = next(
            (item for item in clusters
             if abs(price - item["price"]) / item["price"] <= tolerance_pct),
            None,
        )
        if match is None:
            clusters.append({"prices": [price], "indices": [index], "price": price})
        else:
            match["prices"].append(price)
            match["indices"].append(index)
            match["price"] = sum(match["prices"]) / len(match["prices"])
    return [
        {
            "price": round(sum(item["prices"]) / len(item["prices"]), 10),
            "touches": len(item["prices"]),
            "first_pivot_index": min(item["indices"]),
            "last_pivot_index": max(item["indices"]),
        }
        for item in clusters
    ]


def analyze_support_resistance(
    candles: list[list[Any]],
    pivot_left: int = 3,
    pivot_right: int = 3,
    tolerance_pct: float = 0.003,
) -> dict[str, Any]:
    if pivot_left < 1 or pivot_right < 1:
        raise ValueError("pivot_left and pivot_right must be at least 1")
    if not 0 < tolerance_pct <= 0.05:
        raise ValueError("tolerance_pct must be between 0 and 0.05")
    if len(candles) < pivot_left + pivot_right + 3:
        return {"status": "INCOMPLETE", "reason": "Insufficient candles for pivot analysis"}
    highs = [float(row[2]) for row in candles]
    lows = [float(row[3]) for row in candles]
    closes = [float(row[4]) for row in candles]
    if any(value <= 0 for value in highs + lows + closes):
        raise ValueError("OHLC prices must be positive")
    high_points = [(highs[i], i) for i in _pivot_indices(highs, pivot_left, pivot_right, "high")]
    low_points = [(lows[i], i) for i in _pivot_indices(lows, pivot_left, pivot_right, "low")]
    current = closes[-1]
    resistance = [
        item for item in _cluster_levels(high_points, tolerance_pct)
        if item["price"] >= current
    ]
    support = [
        item for item in _cluster_levels(low_points, tolerance_pct)
        if item["price"] <= current
    ]
    resistance.sort(key=lambda item: item["price"])
    support.sort(key=lambda item: item["price"], reverse=True)
    return {
        "status": "COMPLETED" if high_points or low_points else "INCOMPLETE",
        "method": "Confirmed local pivots clustered by percentage price tolerance",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "latest_close": current,
        "parameters": {
            "pivot_left": pivot_left,
            "pivot_right": pivot_right,
            "tolerance_pct": tolerance_pct,
        },
        "support": support,
        "resistance": resistance,
        "pivot_counts": {"highs": len(high_points), "lows": len(low_points)},
        "warning": "Levels are historical pivot clusters, not guaranteed barriers. The latest pivot_right candles are not eligible as confirmed pivots.",
    }


def calculate_fibonacci_levels(
    candles: list[list[Any]], pivot_left: int = 3, pivot_right: int = 3
) -> dict[str, Any]:
    if pivot_left < 1 or pivot_right < 1:
        raise ValueError("pivot_left and pivot_right must be at least 1")
    highs = [float(row[2]) for row in candles]
    lows = [float(row[3]) for row in candles]
    if len(candles) < pivot_left + pivot_right + 3:
        return {"status": "INCOMPLETE", "reason": "Insufficient candles for swing detection"}
    high_pivots = _pivot_indices(highs, pivot_left, pivot_right, "high")
    low_pivots = _pivot_indices(lows, pivot_left, pivot_right, "low")
    if not high_pivots or not low_pivots:
        return {"status": "INCOMPLETE", "reason": "No confirmed swing high/low pair found"}
    # Use the most recent confirmed pivot as the end of the latest swing and
    # pair it with the latest opposite pivot preceding it.
    last_high = high_pivots[-1]
    last_low = low_pivots[-1]
    if last_high > last_low:
        start_candidates = [i for i in low_pivots if i < last_high]
        if not start_candidates:
            return {"status": "INCOMPLETE", "reason": "No preceding swing low"}
        start_index, end_index = start_candidates[-1], last_high
        low, high, direction = lows[start_index], highs[end_index], "UP"
    else:
        start_candidates = [i for i in high_pivots if i < last_low]
        if not start_candidates:
            return {"status": "INCOMPLETE", "reason": "No preceding swing high"}
        start_index, end_index = start_candidates[-1], last_low
        high, low, direction = highs[start_index], lows[end_index], "DOWN"
    if high <= low:
        return {"status": "INCOMPLETE", "reason": "Invalid swing range"}
    span = high - low
    ratios = (0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0)
    if direction == "UP":
        levels = {str(r): round(high - span * r, 10) for r in ratios}
        extensions = {str(r): round(low + span * r, 10) for r in (1.272, 1.618, 2.0)}
    else:
        levels = {str(r): round(low + span * r, 10) for r in ratios}
        extensions = {str(r): round(high - span * r, 10) for r in (1.272, 1.618, 2.0)}
    return {
        "status": "COMPLETED",
        "method": "Latest confirmed pivot pair; standard Fibonacci ratios",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "swing": {
            "direction": direction,
            "start_index": start_index,
            "end_index": end_index,
            "swing_low": low,
            "swing_high": high,
            "range": span,
        },
        "retracement_levels": levels,
        "extension_levels": extensions,
        "warning": "Levels depend on the selected swing pivots; alternative swing-selection methods may produce different levels. These are reference levels, not price predictions.",
    }
