from app.services.volume_structure import (
    analyze_market_structure,
    calculate_volume_profile,
    calculate_vwap,
)


def candle(open_, high, low, close, volume):
    return [0, str(open_), str(high), str(low), str(close), str(volume)]


def test_vwap_is_volume_weighted_and_anchorable():
    rows = [candle(9, 11, 9, 10, 10), candle(19, 21, 19, 20, 30)]
    result = calculate_vwap(rows)
    assert result["status"] == "COMPLETED"
    assert result["latest_vwap"] == 17.5
    anchored = calculate_vwap(rows, anchor_index=1)
    assert anchored["latest_vwap"] == 20.0


def test_volume_profile_reports_poc_and_value_area():
    rows = [
        candle(10, 12, 9, 11, 100),
        candle(11, 14, 10, 13, 300),
        candle(13, 16, 12, 15, 200),
    ]
    result = calculate_volume_profile(rows, bins=10)
    assert result["status"] == "COMPLETED"
    assert result["poc"]["volume"] > 0
    assert result["vah"] >= result["val"]
    assert abs(sum(x["volume"] for x in result["profile"]) - 600) < 1e-8


def test_market_structure_returns_confirmed_swings():
    rows = [
        candle(10, 11, 9, 10, 10), candle(10, 12, 10, 11, 10),
        candle(11, 15, 11, 14, 10), candle(14, 14, 10, 11, 10),
        candle(11, 13, 9, 10, 10), candle(10, 12, 10, 11, 10),
        candle(11, 14, 11, 13, 10), candle(13, 13, 10, 12, 10),
        candle(12, 13, 11, 12, 10),
    ]
    result = analyze_market_structure(rows, pivot_left=1, pivot_right=1)
    assert result["status"] == "COMPLETED"
    assert result["latest_confirmed_swing_high"]["price"] > 0
    assert "trend_state" in result


def test_vwap_rejects_invalid_anchor():
    rows = [candle(10, 11, 9, 10, 10)]
    try:
        calculate_vwap(rows, anchor_index=2)
    except ValueError:
        return
    raise AssertionError("Expected invalid anchor index")
