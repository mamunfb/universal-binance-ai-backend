from app.indicators import calculate_indicators


def test_indicator_values_on_rising_series():
    closes = [100.0 + index for index in range(60)]
    result = calculate_indicators(closes)

    assert result["latest_close"] == 159.0
    assert result["ema_20"] is not None
    assert result["ema_50"] is not None
    assert result["ema_200"] is None
    assert result["rsi_14_wilder"] == 100.0
    assert result["macd_12_26"] is not None
    assert result["macd_signal_9"] is not None
    assert result["bollinger_20_2"]["upper"] > result["bollinger_20_2"]["middle"]


def test_indicators_reject_non_positive_prices():
    try:
        calculate_indicators([10.0, 0.0, 11.0])
    except ValueError:
        return
    raise AssertionError("Expected non-positive price validation")
