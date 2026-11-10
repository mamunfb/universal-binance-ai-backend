import pytest

from app.services.liquidity_behavior import analyze_liquidity_behavior


def snapshots():
    return [
        {
            "event_time_ms": 1000, "update_id": 10, "mid_price": 100.0,
            "bids": [[99.9, 200], [99.8, 100]],
            "asks": [[100.1, 200], [100.2, 100]],
        },
        {
            "event_time_ms": 2000, "update_id": 20, "mid_price": 100.001,
            "bids": [[99.9, 200], [99.8, 100]],
            "asks": [[100.1, 200], [100.2, 100]],
        },
    ]


def test_detects_buy_pressure_with_stable_ask_depth_absorption_candidate():
    trades = [
        {"trade_time_ms": 1500, "price": 100.1, "notional": 20000, "aggressor_side": "BUY"},
    ]
    result = analyze_liquidity_behavior(
        snapshots(), trades, "SPOT", "BTCUSDT",
        min_aggressive_notional=10000,
    )
    assert result["status"] == "COMPLETED"
    assert result["aggressive_trade_flow"]["buy_notional_proxy"] == 20000
    assert result["absorption_candidates"][0]["aggressor_side"] == "BUY"


def test_detects_bid_withdrawal_candidate_when_trade_flow_is_low():
    rows = snapshots()
    rows[1]["bids"] = [[99.8, 100]]
    trades = [
        {"trade_time_ms": 1500, "price": 100.1, "notional": 100, "aggressor_side": "BUY"},
    ]
    result = analyze_liquidity_behavior(
        rows, trades, "SPOT", "BTCUSDT", min_removed_notional=1000,
    )
    assert result["liquidity_withdrawal_candidates"]
    assert result["liquidity_withdrawal_candidates"][0]["classification"] == "PULLING_CANDIDATE_LOW_MATCHED_TRADE_FLOW"


def test_trade_consumption_not_mislabelled_as_pull_candidate():
    rows = snapshots()
    rows[1]["bids"] = [[99.8, 100]]
    trades = [
        {"trade_time_ms": 1500, "price": 99.9, "notional": 5000, "aggressor_side": "SELL"},
    ]
    result = analyze_liquidity_behavior(
        rows, trades, "USD_M", "BTCUSDT", min_removed_notional=1000,
    )
    assert result["liquidity_withdrawal_candidates"][0]["classification"] == "TRADE_CONSUMPTION_OR_MIXED"


def test_insufficient_data_and_invalid_arguments():
    assert analyze_liquidity_behavior([], [], "SPOT", "BTCUSDT")["status"] == "INSUFFICIENT_DATA"
    with pytest.raises(ValueError):
        analyze_liquidity_behavior(snapshots(), [], "BAD", "BTCUSDT")
    with pytest.raises(ValueError):
        analyze_liquidity_behavior(snapshots(), [], "SPOT", "BTCUSDT", min_removed_notional=-1)
