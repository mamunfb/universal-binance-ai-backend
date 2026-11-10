import pytest

from app.services.order_book_intelligence import analyze_order_book


def _book():
    return {
        "lastUpdateId": 123,
        "bids": [["100", "10"], ["99.9", "1"], ["99.8", "1"], ["99.7", "1"]],
        "asks": [["100.1", "1"], ["100.2", "1"], ["100.3", "1"], ["100.4", "1"]],
    }


def test_order_book_intelligence_reports_depth_spread_microprice_and_walls():
    result = analyze_order_book(_book(), "SPOT", "BTCUSDT", levels=4, wall_multiplier=2)
    assert result["status"] == "COMPLETED"
    assert result["best_bid"] == 100
    assert result["best_ask"] == 100.1
    assert result["spread"] == pytest.approx(0.1)
    assert result["depth"]["bid_notional"] > result["depth"]["ask_notional"]
    assert result["depth"]["imbalance"] > 0
    assert result["microprice"] > result["mid_price"]
    assert result["large_visible_order_candidates"][0]["side"] == "BID"
    assert "5" in result["near_mid_depth_bands_bps"]
    assert len(result["cumulative_depth"]["bids"]) == 4


def test_order_book_intelligence_rejects_crossed_and_empty_books():
    crossed = analyze_order_book(
        {"bids": [["101", "1"]], "asks": [["100", "1"]]}, "USD_M", "BTCUSDT"
    )
    assert crossed["status"] == "INCOMPLETE"
    assert crossed["reason"] == "CROSSED_OR_LOCKED_BOOK"
    empty = analyze_order_book({"bids": [], "asks": []}, "SPOT", "BTCUSDT")
    assert empty["reason"] == "MISSING_VALID_BID_OR_ASK_LEVELS"


def test_order_book_intelligence_rejects_invalid_levels_and_arguments():
    result = analyze_order_book({
        "bids": [["nan", "1"], ["99", "2"]],
        "asks": [["101", "inf"], ["102", "1"]],
    }, "SPOT", "BTCUSDT", levels=2)
    assert result["status"] == "COMPLETED"
    assert result["rejected_rows"] == {"bids": 1, "asks": 1}
    with pytest.raises(ValueError):
        analyze_order_book(_book(), "BAD", "BTCUSDT")
    with pytest.raises(ValueError):
        analyze_order_book(_book(), "SPOT", "BTCUSDT", wall_multiplier=0)
