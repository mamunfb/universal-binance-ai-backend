from app.services.price_levels import analyze_support_resistance, calculate_fibonacci_levels


def candle(high, low, close=None):
    close = close if close is not None else (high + low) / 2
    return [0, "0", str(high), str(low), str(close), "0"]


def test_support_resistance_detects_pivot_clusters():
    values = [
        candle(10, 8), candle(11, 9), candle(12, 10), candle(11, 9),
        candle(10, 8), candle(11, 9), candle(12.01, 10), candle(11, 9),
        candle(10, 8), candle(10, 9, 9.5),
    ]
    result = analyze_support_resistance(values, pivot_left=1, pivot_right=1, tolerance_pct=0.01)
    assert result["status"] == "COMPLETED"
    assert result["resistance"][0]["touches"] >= 2


def test_fibonacci_up_swing_levels():
    values = [
        candle(10, 8), candle(11, 9), candle(12, 10), candle(11, 9),
        candle(10, 8), candle(11, 9), candle(13, 10), candle(12, 9),
        candle(11, 8), candle(10, 7),
    ]
    result = calculate_fibonacci_levels(values, pivot_left=1, pivot_right=1)
    assert result["status"] == "COMPLETED"
    assert result["swing"]["direction"] == "DOWN"
    assert "0.618" in result["retracement_levels"]


def test_price_levels_reject_bad_parameters():
    values = [candle(10, 8)] * 8
    try:
        analyze_support_resistance(values, pivot_left=0)
    except ValueError:
        return
    raise AssertionError("Expected invalid pivot parameter")
