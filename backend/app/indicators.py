from math import sqrt
from typing import Any


def _ema_series(values: list[float], period: int) -> list[float | None]:
    if period <= 0:
        raise ValueError("period must be positive")
    output: list[float | None] = [None] * len(values)
    if len(values) < period:
        return output
    current = sum(values[:period]) / period
    output[period - 1] = current
    multiplier = 2.0 / (period + 1.0)
    for index in range(period, len(values)):
        current = (values[index] - current) * multiplier + current
        output[index] = current
    return output


def _rsi(values: list[float], period: int = 14) -> float | None:
    if len(values) <= period:
        return None
    gains = [max(values[i] - values[i - 1], 0.0) for i in range(1, period + 1)]
    losses = [max(values[i - 1] - values[i], 0.0) for i in range(1, period + 1)]
    average_gain = sum(gains) / period
    average_loss = sum(losses) / period
    for index in range(period + 1, len(values)):
        gain = max(values[index] - values[index - 1], 0.0)
        loss = max(values[index - 1] - values[index], 0.0)
        average_gain = ((average_gain * (period - 1)) + gain) / period
        average_loss = ((average_loss * (period - 1)) + loss) / period
    if average_loss == 0:
        return 100.0 if average_gain > 0 else 50.0
    relative_strength = average_gain / average_loss
    return 100.0 - (100.0 / (1.0 + relative_strength))


def calculate_indicators(closes: list[float]) -> dict[str, Any]:
    """Return latest EMA, RSI, MACD and Bollinger values from chronological closes."""
    if any(value <= 0 for value in closes):
        raise ValueError("close prices must be positive")
    if len(closes) < 2:
        raise ValueError("at least two close prices are required")

    ema20 = _ema_series(closes, 20)[-1]
    ema50 = _ema_series(closes, 50)[-1]
    ema100 = _ema_series(closes, 100)[-1]
    ema200 = _ema_series(closes, 200)[-1]
    rsi14 = _rsi(closes, 14)
    sma20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else None
    sma50 = sum(closes[-50:]) / 50 if len(closes) >= 50 else None
    sma100 = sum(closes[-100:]) / 100 if len(closes) >= 100 else None
    sma200 = sum(closes[-200:]) / 200 if len(closes) >= 200 else None

    fast = _ema_series(closes, 12)
    slow = _ema_series(closes, 26)
    macd_points = [
        fast[i] - slow[i]
        for i in range(len(closes))
        if fast[i] is not None and slow[i] is not None
    ]
    macd = macd_points[-1] if macd_points else None
    signal_points = _ema_series(macd_points, 9) if macd_points else []
    signal = signal_points[-1] if signal_points else None
    histogram = macd - signal if macd is not None and signal is not None else None

    middle = upper = lower = None
    if len(closes) >= 20:
        window = closes[-20:]
        middle = sum(window) / 20
        variance = sum((value - middle) ** 2 for value in window) / 20
        deviation = sqrt(variance)
        upper = middle + (2 * deviation)
        lower = middle - (2 * deviation)

    return {
        "input_close_count": len(closes),
        "latest_close": closes[-1],
        "ema_20": ema20,
        "ema_50": ema50,
        "ema_100": ema100,
        "ema_200": ema200,
        "sma_20": sma20,
        "sma_50": sma50,
        "sma_100": sma100,
        "sma_200": sma200,
        "rsi_14_wilder": rsi14,
        "macd_12_26": macd,
        "macd_signal_9": signal,
        "macd_histogram": histogram,
        "bollinger_20_2": {
            "middle": middle,
            "upper": upper,
            "lower": lower,
        },
        "method_notes": {
            "ema": "EMA seeded with the first-period simple average",
            "rsi": "Wilder smoothing",
            "bollinger": "20-period population standard deviation, 2 deviations",
            "unavailable_values": "null means insufficient input history",
        },
    }
