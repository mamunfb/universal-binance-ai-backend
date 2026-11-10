from app.services.market_structure_confluence import analyze_market_structure_confluence


def test_confluence_reports_conflicting_directional_evidence():
    result = analyze_market_structure_confluence(
        "USD_M", "BTCUSDT", "1h",
        {"status": "COMPLETED", "structure": "BULLISH",
         "structure_break": {"type": "BOS", "direction": "BULLISH", "confirmed_by_close": True}},
        {"status": "COMPLETED", "market_regime": "TREND", "directional_context": "UP"},
        {"status": "COMPLETED", "trade_count": 20,
         "aggressor_flow": {"net_cvd_quantity": -5}},
        {"status": "COMPLETED", "cvd_agreement": "ALL_TIMEFRAMES_SELL_CVD"},
        {"status": "COMPLETED", "sweep_candidates": [{
            "direction": "BULLISH_AFTER_SELL_SIDE_SWEEP",
            "sweep_type": "SELL_SIDE_LIQUIDITY_SWEEP_CANDIDATE",
            "sweep_time_ms": 123, "confirmation_status": "SINGLE_SOURCE_CANDIDATE",
            "evidence_count": 1,
        }]},
    )
    assert result["confluence"]["bias"] == "MIXED"
    assert result["confluence"]["alignment"] == "CONFLICTING_EVIDENCE"
    assert result["confluence"]["bullish_evidence_count"] == 4
    assert result["confluence"]["bearish_evidence_count"] == 2
    assert result["confluence"]["is_prediction"] is False


def test_missing_sources_do_not_vote_against_available_direction():
    result = analyze_market_structure_confluence(
        "SPOT", "ETHUSDT", "15m",
        {"status": "COMPLETED", "structure": "BEARISH",
         "structure_break": {"type": "NO_CONFIRMED_BREAK", "direction": "NONE"}},
        {"status": "INSUFFICIENT_DATA", "market_regime": "UNKNOWN"},
        {"status": "INSUFFICIENT_DATA"},
        {"status": "INSUFFICIENT_DATA", "cvd_agreement": "INSUFFICIENT_TIMEFRAME_DATA"},
        {"status": "NO_RECENT_SWEEP_CANDIDATE", "sweep_candidates": []},
    )
    assert result["confluence"]["bias"] == "BEARISH"
    assert result["confluence"]["alignment"] == "BEARISH_EVIDENCE_ALIGNMENT"
    assert result["confluence"]["directional_source_count"] == 1


def test_no_directional_evidence_returns_unknown():
    empty = {"status": "INSUFFICIENT_DATA"}
    result = analyze_market_structure_confluence(
        "SPOT", "BTCUSDT", "1h", empty, empty, empty, empty, empty,
    )
    assert result["confluence"]["bias"] == "UNKNOWN"
    assert result["confluence"]["alignment"] == "INSUFFICIENT_DIRECTIONAL_EVIDENCE"



def test_confluence_preserves_volume_profile_and_timeframe_evidence_details():
    result = analyze_market_structure_confluence(
        "USD_M", "BTCUSDT", "1h",
        {
            "status": "COMPLETED", "structure": "BULLISH", "current_close": 105.0,
            "swing_points": {
                "latest_high": {"price": 104.0}, "latest_low": {"price": 99.0},
            },
            "structure_break": {
                "type": "BOS", "direction": "BULLISH",
                "confirmed_by_close": True, "broken_level": {"price": 104.0},
            },
        },
        {
            "status": "COMPLETED", "market_regime": "TREND",
            "directional_context": "UP", "volatility_regime": "NORMAL_VOLATILITY",
            "structure_regime": "TREND", "metrics": {"path_efficiency": 0.8},
        },
        {
            "status": "COMPLETED", "trade_count": 12,
            "aggressor_flow": {"net_cvd_quantity": 4.0},
            "price_cvd_divergence": {"classification": "NO_OPPOSING_PRICE_CVD_DIVERGENCE"},
            "volume_profile": {
                "poc": {"price_mid": 103.0},
                "value_area": {"val": 101.0, "vah": 105.0},
            },
            "coverage": {"returned_trade_count": 12},
        },
        {
            "status": "COMPLETED", "cvd_agreement": "ALL_TIMEFRAMES_BUY_CVD",
            "completed_timeframe_count": 2, "timeframe_count": 2,
            "timeframes": [{
                "period": "15m", "status": "COMPLETED", "net_cvd_quantity": 2.0,
                "price_cvd_divergence": "NO_OPPOSING_PRICE_CVD_DIVERGENCE",
                "poc": {"price_mid": 102.0},
                "value_area": {"val": 100.0, "vah": 104.0},
                "coverage": {"returned_trade_count": 5},
            }],
        },
        {
            "status": "COMPLETED", "sweep_candidates": [{
                "direction": "BULLISH_AFTER_SELL_SIDE_SWEEP",
                "sweep_type": "SELL_SIDE_LIQUIDITY_SWEEP_CANDIDATE",
                "sweep_time_ms": 123, "confirmation_status": "MULTI_SOURCE_CANDIDATE",
                "evidence_count": 2,
                "aggressor_flow": {"confirmation": "ALIGNED_AGGRESSOR_FLOW"},
                "volume_profile": {"poc": {"price_mid": 100.0}},
                "order_book_context": {"status": "SAMPLED_DEPTH_CHANGED"},
                "derivatives_context": {"open_interest": None, "funding": None},
            }],
        },
    )
    sources = {item["source"]: item for item in result["evidence"]}
    assert sources["ORDER_FLOW_CVD"]["detail"]["poc"]["price_mid"] == 103.0
    assert sources["ORDER_FLOW_CVD"]["detail"]["value_area"]["vah"] == 105.0
    assert sources["MULTI_TIMEFRAME_CVD"]["detail"]["timeframes"][0]["period"] == "15m"
    assert sources["LIQUIDITY_SWEEP"]["detail"]["aggressor_flow"]["confirmation"] == "ALIGNED_AGGRESSOR_FLOW"
    assert sources["MARKET_STRUCTURE"]["detail"]["latest_swing_high"]["price"] == 104.0
