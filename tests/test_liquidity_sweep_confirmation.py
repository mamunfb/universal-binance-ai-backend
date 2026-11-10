from app.services.liquidity_sweep_confirmation import analyze_liquidity_sweep_confirmation


def make_candles():
    rows = []
    for i in range(40):
        rows.append({
            "open_time_ms": i * 60_000, "open": 100.0, "high": 102.0,
            "low": 98.0, "close": 100.0,
        })
    rows[10].update({"high": 105.0, "low": 99.0})
    rows[13].update({"high": 106.0, "low": 99.0, "close": 104.0})
    return rows


def test_detects_buy_side_sweep_and_aligned_trade_flow():
    candles = make_candles()
    sweep_time = candles[13]["open_time_ms"]
    trades = [
        {"trade_time_ms": sweep_time + 1_000, "price": 100.0, "quantity": 3.0, "notional": 300.0, "aggressor_side": "SELL"},
        {"trade_time_ms": sweep_time + 2_000, "price": 100.1, "quantity": 1.0, "notional": 100.1, "aggressor_side": "BUY"},
    ]
    result = analyze_liquidity_sweep_confirmation(
        candles, trades, [], "USD_M", "BTCUSDT"
    )
    assert result["status"] == "COMPLETED"
    candidate = next(
        item for item in result["sweep_candidates"]
        if item["sweep_type"] == "BUY_SIDE_LIQUIDITY_SWEEP_CANDIDATE"
        and item["level"] == 105.0
    )
    assert candidate["aggressor_flow"]["confirmation"] == "OPPOSING_AGGRESSOR_FLOW"
    assert candidate["confirmation_status"] == "OHLC_ONLY_CANDIDATE"
    assert candidate["volume_profile"]["status"] == "COMPLETED"
    assert candidate["volume_profile"]["poc"] is not None


def test_pairs_order_book_and_derivatives_only_within_explicit_time_lag():
    candles = make_candles()
    sweep_time = candles[13]["open_time_ms"]
    books = [
        {"event_time_ms": sweep_time, "bids": [[100, 10]], "asks": [[101, 10]]},
        {"event_time_ms": sweep_time + 300_000, "bids": [[100, 8]], "asks": [[101, 12]]},
    ]
    oi = [{"timestamp_ms": sweep_time + 1_000, "sum_open_interest": 100, "sum_open_interest_value": 10000}]
    funding = [{"funding_time_ms": sweep_time + 2_000, "funding_rate": 0.0001}]
    result = analyze_liquidity_sweep_confirmation(
        candles, [], books, "USD_M", "BTCUSDT", oi, funding
    )
    candidate = next(
        item for item in result["sweep_candidates"]
        if item["sweep_type"] == "BUY_SIDE_LIQUIDITY_SWEEP_CANDIDATE"
        and item["level"] == 105.0
    )
    assert candidate["order_book_context"]["status"] == "SAMPLED_DEPTH_CHANGED"
    assert candidate["derivatives_context"]["open_interest"]["timestamp_ms"] == sweep_time + 1_000
    assert candidate["derivatives_context"]["funding"]["funding_time_ms"] == sweep_time + 2_000


def test_no_derivatives_forward_fill_when_timestamp_is_outside_tolerance():
    candles = make_candles()
    sweep_time = candles[13]["open_time_ms"]
    result = analyze_liquidity_sweep_confirmation(
        candles, [], [], "USD_M", "BTCUSDT",
        [{"timestamp_ms": sweep_time + 3_600_001, "sum_open_interest": 100}],
        [{"funding_time_ms": sweep_time + 3_600_001, "funding_rate": 0.001}],
    )
    candidate = next(
        item for item in result["sweep_candidates"]
        if item["sweep_type"] == "BUY_SIDE_LIQUIDITY_SWEEP_CANDIDATE"
        and item["level"] == 105.0
    )
    assert candidate["derivatives_context"]["open_interest"] is None
    assert candidate["derivatives_context"]["funding"] is None


def test_rejects_inconsistent_ohlc():
    candles = make_candles()
    candles[0]["high"] = 90
    try:
        analyze_liquidity_sweep_confirmation(candles, [], [], "SPOT", "BTCUSDT")
    except ValueError as exc:
        assert "Inconsistent candle" in str(exc)
    else:
        raise AssertionError("Expected invalid OHLC to be rejected")
