from app.services.catalyst_analysis import analyze_catalysts


def test_hack_is_bearish_high_impact_but_unverified_not_signal_eligible():
    item = {
        "title": "Protocol hacked after security breach",
        "summary": "Funds drained in exploit",
        "verification_status": "UNVERIFIED",
    }
    result = analyze_catalysts([item])[0]["catalyst"]
    assert "HACK_EXPLOIT" in result["types"]
    assert result["direction"] == "BEARISH"
    assert result["impact_level"] == "HIGH"
    assert result["eligible_for_signal_review"] is False


def test_confirmed_listing_can_be_signal_review_candidate():
    item = {
        "title": "Binance lists Example token",
        "summary": "New listing announced",
        "verification_status": "CONFIRMED",
    }
    result = analyze_catalysts([item])[0]["catalyst"]
    assert "LISTING" in result["types"]
    assert result["direction"] == "BULLISH"
    assert result["eligible_for_signal_review"] is True


def test_upgrade_is_mixed_without_context():
    result = analyze_catalysts([{
        "title": "Network upgrade announced",
        "verification_status": "PARTIALLY_CONFIRMED",
    }])[0]["catalyst"]
    assert result["direction"] == "MIXED"
    assert result["eligible_for_signal_review"] is False


def test_unmatched_news_does_not_receive_a_score():
    result = analyze_catalysts([{
        "title": "Community shares weekly update",
        "verification_status": "UNVERIFIED",
    }])[0]["catalyst"]
    assert result["status"] == "NO_RULE_MATCH"
    assert result["heuristic_score"] is None


def test_keyword_triage_does_not_fabricate_weighted_catalyst_score():
    result = analyze_catalysts([{
        "title": "Binance lists Example token",
        "verification_status": "CONFIRMED",
    }])[0]["catalyst"]
    assert result["heuristic_score"] is not None
    assert result["catalyst_score_0_100"] is None
    assert result["catalyst_score_status"] == "NOT_ESTABLISHED"
    assert all(value is None for value in result["catalyst_score_components"].values())
