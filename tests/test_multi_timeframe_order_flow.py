from app.services.multi_timeframe_order_flow import analyze_multi_timeframe_order_flow


def test_multi_timeframe_order_flow_compares_requested_windows():
    end = 2_000_000
    rows = [
        {"trade_time_ms": end - 120_000, "price": 100, "quantity": 2,
         "notional": 200, "aggressor_side": "BUY"},
        {"trade_time_ms": end - 60_000, "price": 100.1, "quantity": 1,
         "notional": 100.1, "aggressor_side": "BUY"},
        {"trade_time_ms": end - 10_000, "price": 100.2, "quantity": 1,
         "notional": 100.2, "aggressor_side": "SELL"},
    ]
    result = analyze_multi_timeframe_order_flow(
        rows, "USD_M", "BTCUSDT", end, ["5m", "15m"]
    )
    assert result["status"] == "COMPLETED"
    assert result["timeframe_count"] == 2
    assert result["completed_timeframe_count"] == 2
    assert result["timeframes"][0]["period"] == "5m"
    assert result["timeframes"][1]["period"] == "15m"
    assert result["cvd_agreement"] in {
        "ALL_TIMEFRAMES_BUY_CVD", "ALL_TIMEFRAMES_SELL_CVD",
        "MIXED_BUY_SELL_CVD", "MIXED_OR_FLAT_CVD",
    }


def test_multi_timeframe_reports_missing_windows():
    result = analyze_multi_timeframe_order_flow(
        [], "SPOT", "BTCUSDT", 2_000_000, ["5m", "1h"]
    )
    assert result["status"] == "INSUFFICIENT_DATA"
    assert result["cvd_agreement"] == "INSUFFICIENT_TIMEFRAME_DATA"
    assert result["completed_timeframe_count"] == 0


def test_multi_timeframe_validates_periods():
    import pytest
    with pytest.raises(ValueError):
        analyze_multi_timeframe_order_flow([], "SPOT", "BTCUSDT", 1000, ["5m", "5m"])
    with pytest.raises(ValueError):
        analyze_multi_timeframe_order_flow([], "SPOT", "BTCUSDT", 1000, ["2d"])
