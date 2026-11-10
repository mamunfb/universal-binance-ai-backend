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


def test_indicators_include_ema_100_and_sma_periods():
    closes = [100.0 + index for index in range(250)]
    result = calculate_indicators(closes)

    assert result["ema_100"] is not None
    assert result["ema_200"] is not None
    assert result["sma_20"] == sum(closes[-20:]) / 20
    assert result["sma_50"] == sum(closes[-50:]) / 50
    assert result["sma_100"] == sum(closes[-100:]) / 100
    assert result["sma_200"] == sum(closes[-200:]) / 200


def test_sma_and_ema_return_null_when_history_is_insufficient():
    result = calculate_indicators([100.0 + index for index in range(60)])
    assert result["ema_100"] is None
    assert result["sma_100"] is None
    assert result["sma_200"] is None
