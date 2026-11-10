from app.services.market_evidence import build_market_evidence_snapshot, detect_evidence_conflicts


def _sections():
    multi = {
        "status": "COMPLETED",
        "timeframes": {
            "1d": {"trend_structure": "BULLISH_STRUCTURE"},
            "4h": {"trend_structure": "BULLISH_STRUCTURE"},
        },
    }
    basis = {
        "status": "COMPLETED",
        "source": "test exchange",
        "price_comparison": {
            "status": "COMPLETED", "basis": 2, "basis_percent": 1,
            "relationship": "FUTURES_PREMIUM",
        },
        "funding": {"status": "COMPLETED", "funding_rate": 0.0001,
                    "funding_time_ms": 123, "source": "test funding"},
    }
    derivatives = {
        "status": "COMPLETED", "source": "test derivatives",
        "sections": {
            "open_interest": {"status": "COMPLETED", "data": {"openInterest": "1000"}},
            "open_interest_history": {"status": "COMPLETED", "data": [
                {"sumOpenInterest": "900", "timestamp": 100},
                {"sumOpenInterest": "1000", "timestamp": 200},
            ]},
            "global_long_short_account_ratio": {"status": "COMPLETED",
                                                "data": [{"longShortRatio": "1.2"}]},
            "taker_buy_sell_ratio": {"status": "COMPLETED",
                                     "data": [{"buySellRatio": "1.1"}]},
            "order_book": {"status": "COMPLETED", "data": {
                "status": "COMPLETED", "depth_imbalance": 0.2, "spread_bps": 1.5,
            }},
        },
    }
    volume = {
        "status": "COMPLETED", "source": "test candles",
        "vwap": {"latest_vwap": 100, "latest_close": 101},
        "volume_profile": {"poc": {"price_mid": 99}, "vah": 102, "val": 97},
        "market_structure": {"trend_state": "BULLISH"},
        "warning": "approximate",
    }
    news = {
        "status": "COMPLETED",
        "items": [{
            "title": "Example confirmed listing",
            "url": "https://news.example/item",
            "published_at": "2026-11-10T00:00:00Z",
            "verification_status": "CONFIRMED",
            "catalyst": {"eligible_for_signal_review": True,
                         "direction": "BULLISH", "types": ["LISTING"]},
        }],
    }
    return multi, basis, derivatives, volume, news


def test_market_evidence_aggregates_independent_observations_without_signal():
    sections = _sections()
    result = build_market_evidence_snapshot("btcusdt", *sections)
    assert result["status"] == "COMPLETED"
    assert result["symbol"] == "BTCUSDT"
    assert result["mode"] == "RESEARCH_ONLY_EVIDENCE_SUMMARY"
    assert result["decision"]["status"] == "NO_TRADE_DECISION"
    assert result["decision"]["buy_sell_signal"] is None
    assert result["decision"]["probability"] is None
    categories = {item["category"] for item in result["evidence"]}
    assert {
        "TREND_ALIGNMENT", "SPOT_FUTURES_BASIS", "FUNDING_RATE",
        "OPEN_INTEREST", "OPEN_INTEREST_HISTORY", "GLOBAL_ACCOUNT_RATIO", "TAKER_BUY_SELL_RATIO",
        "ORDER_BOOK_DEPTH", "VOLUME_AND_STRUCTURE", "NEWS_CATALYSTS",
    } <= categories


def test_market_evidence_is_incomplete_when_any_required_section_is_incomplete():
    multi, basis, derivatives, volume, news = _sections()
    derivatives["status"] = "INCOMPLETE"
    derivatives["sections"]["open_interest"]["status"] = "FAILED"
    result = build_market_evidence_snapshot("BTCUSDT", multi, basis, derivatives, volume, news)
    assert result["status"] == "INCOMPLETE"
    assert result["section_status"]["derivatives"] == "INCOMPLETE"
    assert any("OPEN_INTEREST" in item for item in result["limitations"])


def test_unconfirmed_news_is_not_promoted_to_confirmed_candidate():
    multi, basis, derivatives, volume, news = _sections()
    news["items"][0]["verification_status"] = "UNVERIFIED"
    result = build_market_evidence_snapshot("BTCUSDT", multi, basis, derivatives, volume, news)
    news_evidence = next(x for x in result["evidence"] if x["category"] == "NEWS_CATALYSTS")
    assert news_evidence["status"] == "NO_CONFIRMED_CANDIDATES"
    assert news_evidence["confirmed_signal_review_candidates"] == 0


def test_failed_news_feed_is_reported_as_incomplete():
    multi, basis, derivatives, volume, news = _sections()
    news["status"] = "INCOMPLETE"
    result = build_market_evidence_snapshot("BTCUSDT", multi, basis, derivatives, volume, news)
    news_evidence = next(x for x in result["evidence"] if x["category"] == "NEWS_CATALYSTS")
    assert news_evidence["status"] == "INCOMPLETE"
    assert any("news-feed" in item for item in result["limitations"])


def test_open_interest_history_change_is_descriptive_not_directional():
    sections = _sections()
    result = build_market_evidence_snapshot("BTCUSDT", *sections)
    oi = next(item for item in result["evidence"] if item["category"] == "OPEN_INTEREST_HISTORY")
    assert oi["status"] == "OBSERVED"
    assert oi["change_percent"] == 100 / 9
    assert "does not identify long or short" in oi["warning"]


def test_conflict_detector_reports_opposing_timeframe_structures():
    sections = list(_sections())
    sections[0]["timeframes"]["4h"]["trend_structure"] = "BEARISH_STRUCTURE"
    result = build_market_evidence_snapshot("BTCUSDT", *sections)
    conflict = next(
        item for item in result["conflict_analysis"]["conflicts"]
        if item["rule_id"] == "TREND_TIMEFRAME_DIVERGENCE"
    )
    assert conflict["observations"] == {
        "1d": "BULLISH_STRUCTURE", "4h": "BEARISH_STRUCTURE"
    }


def test_conflict_detector_reports_basis_and_funding_divergence():
    sections = list(_sections())
    sections[1]["funding"]["funding_rate"] = -0.0001
    sections[1]["funding"]["sign"] = "NEGATIVE"
    result = build_market_evidence_snapshot("BTCUSDT", *sections)
    ids = {item["rule_id"] for item in result["conflict_analysis"]["conflicts"]}
    assert "BASIS_FUNDING_DIVERGENCE" in ids


def test_conflict_detector_reports_oi_growth_with_taker_sell_imbalance_as_tension():
    sections = list(_sections())
    sections[2]["sections"]["taker_buy_sell_ratio"]["data"] = [{"buySellRatio": "0.8"}]
    result = build_market_evidence_snapshot("BTCUSDT", *sections)
    conflict = next(
        item for item in result["conflict_analysis"]["conflicts"]
        if item["rule_id"] == "OPEN_INTEREST_TAKER_FLOW_TENSION"
    )
    assert conflict["severity"] == "INFO"
    assert "does not reveal which side" in conflict["explanation"]


def test_conflict_detector_reports_trend_and_market_structure_divergence():
    sections = list(_sections())
    sections[3]["market_structure"]["trend_state"] = "BEARISH"
    result = build_market_evidence_snapshot("BTCUSDT", *sections)
    ids = {item["rule_id"] for item in result["conflict_analysis"]["conflicts"]}
    assert "TREND_STRUCTURE_DIVERGENCE" in ids


def test_conflict_detector_reports_opposing_confirmed_news_candidate():
    sections = list(_sections())
    sections[4]["items"][0]["catalyst"]["direction"] = "BEARISH"
    result = build_market_evidence_snapshot("BTCUSDT", *sections)
    ids = {item["rule_id"] for item in result["conflict_analysis"]["conflicts"]}
    assert "CONFIRMED_NEWS_TREND_DIVERGENCE" in ids


def test_conflict_detector_marks_missing_evidence_checks_incomplete():
    result = detect_evidence_conflicts([])
    assert result["status"] == "NO_RULED_CONFLICT_FOUND"
    assert all(item["status"] == "INSUFFICIENT_DATA" for item in result["rule_checks"])
