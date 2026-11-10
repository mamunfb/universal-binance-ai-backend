from app.services.order_flow_intelligence import analyze_order_flow


def trade(ts, price, qty, side):
    return {"trade_time_ms": ts, "price": price, "quantity": qty,
            "notional": price * qty, "aggressor_side": side}


def test_order_flow_builds_profile_cvd_and_divergence():
    rows = [
        trade(1000, 100.0, 2, "BUY"),
        trade(2000, 100.0, 1, "SELL"),
        trade(3000, 100.1, 1, "SELL"),
        trade(4000, 100.2, 3, "SELL"),
    ]
    result = analyze_order_flow(rows, "SPOT", "BTCUSDT", 1000, 4000, 10, 70)
    assert result["status"] == "COMPLETED"
    assert result["aggressor_flow"]["net_cvd_quantity"] == 2 - 5
    assert result["price_cvd_divergence"]["classification"] == "PRICE_UP_CVD_DOWN_CANDIDATE"
    profile = result["volume_profile"]
    assert profile["poc"]["volume_notional_proxy"] > 0
    assert profile["value_area"]["val"] <= profile["value_area"]["vah"]
    assert len(profile["buckets"]) >= 1


def test_order_flow_returns_insufficient_when_no_valid_trades():
    result = analyze_order_flow([], "USD_M", "BTCUSDT", 0, 1000)
    assert result["status"] == "INSUFFICIENT_DATA"


def test_order_flow_filters_out_of_window_and_malformed_rows():
    rows = [
        trade(10, 100, 1, "BUY"),
        trade(100, 100, 1, "BUY"),
        {"trade_time_ms": 150, "price": float("nan"), "quantity": 1,
         "notional": 1, "aggressor_side": "BUY"},
        trade(200, 101, 1, "SELL"),
    ]
    result = analyze_order_flow(rows, "USD_M", "BTCUSDT", 100, 200)
    assert result["trade_count"] == 2
    assert result["rejected_trade_count"] == 2


def test_order_flow_validates_inputs():
    import pytest
    with pytest.raises(ValueError):
        analyze_order_flow([], "BAD", "BTCUSDT", 0, 100)
    with pytest.raises(ValueError):
        analyze_order_flow([], "SPOT", "BTCUSDT", 100, 0)
    with pytest.raises(ValueError):
        analyze_order_flow([], "SPOT", "BTCUSDT", 0, 100, bin_size_bps=0)
