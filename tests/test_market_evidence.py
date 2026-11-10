from app.services.market_evidence import build_market_evidence_snapshot


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
        "OPEN_INTEREST", "GLOBAL_ACCOUNT_RATIO", "TAKER_BUY_SELL_RATIO",
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
