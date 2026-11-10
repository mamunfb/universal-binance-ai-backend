import pytest

from app.services.combined_derivatives_intelligence import CombinedDerivativesIntelligence
from app.services.derivatives_ratio_store import DerivativesRatioStore
from app.services.funding_rates import FundingRateStore
from app.services.open_interest import OpenInterestStore


def oi_row(timestamp, amount):
    return {
        "symbol": "BTCUSDT", "timestamp": timestamp,
        "sumOpenInterest": str(amount), "sumOpenInterestValue": str(amount * 100),
    }


def global_row(timestamp, ratio):
    return {
        "symbol": "BTCUSDT", "timestamp": timestamp,
        "longShortRatio": str(ratio), "longAccount": "0.55", "shortAccount": "0.45",
    }


def taker_row(timestamp, ratio):
    return {
        "symbol": "BTCUSDT", "timestamp": timestamp,
        "buySellRatio": str(ratio), "buyVol": "110", "sellVol": "100",
    }


def build_engine(tmp_path):
    oi = OpenInterestStore(str(tmp_path / "oi.sqlite3"))
    funding = FundingRateStore(str(tmp_path / "funding.sqlite3"))
    ratios = DerivativesRatioStore(str(tmp_path / "ratios.sqlite3"))
    times = [1000, 2000, 3000]
    oi.save("USD_M", "BTCUSDT", "1h", [
        oi_row(times[0], 100), oi_row(times[1], 105), oi_row(times[2], 110),
    ])
    ratios.save("GLOBAL_LONG_SHORT", "BTCUSDT", "1h", [
        global_row(times[0], 1.0), global_row(times[1], 1.1), global_row(times[2], 1.2),
    ])
    ratios.save("TAKER_BUY_SELL", "BTCUSDT", "1h", [
        taker_row(times[0], 0.9), taker_row(times[1], 1.0), taker_row(times[2], 1.1),
    ])
    funding.save("USD_M", "BTCUSDT", [{
        "symbol": "BTCUSDT", "fundingTime": 2500,
        "fundingRate": "0.0001", "markPrice": "60000",
    }])
    return CombinedDerivativesIntelligence(oi, funding, ratios), oi, ratios


def test_combined_analysis_joins_exact_timestamps_and_separates_funding(tmp_path):
    engine, _, _ = build_engine(tmp_path)
    result = engine.analyze("btcusdt", "1h", 10)
    assert result["status"] == "COMPLETED"
    assert result["coverage"]["exact_timestamp_matches"] == 3
    assert result["changes_over_aligned_window"]["open_interest_percent"] == 10
    assert result["latest_positioning_observations"]["account_count_comparison"] == "MORE_LONG_ACCOUNTS_THAN_SHORT_ACCOUNTS"
    assert result["latest_positioning_observations"]["taker_volume_comparison"] == "MORE_AGGRESSIVE_BUY_VOLUME"
    assert result["funding"]["latest_event"]["funding_time_ms"] == 2500
    assert "not position size" in result["interpretation_warnings"][0]


def test_combined_analysis_does_not_forward_fill_missing_ratio_timestamps(tmp_path):
    engine, _, ratios = build_engine(tmp_path)
    ratios.save("TAKER_BUY_SELL", "BTCUSDT", "1h", [taker_row(1000, 0.9), taker_row(3000, 1.1)])
    result = engine.analyze("BTCUSDT", "1h", 10)
    assert result["coverage"]["exact_timestamp_matches"] == 2
    assert [row["timestamp_ms"] for row in result["aligned_observations"]] == [1000, 3000]


def test_combined_analysis_returns_insufficient_if_only_one_common_timestamp(tmp_path):
    engine, _, ratios = build_engine(tmp_path)
    ratios.save("TAKER_BUY_SELL", "BTCUSDT", "1h", [taker_row(1000, 0.9)])
    result = engine.analyze("BTCUSDT", "1h", 10)
    assert result["status"] == "INSUFFICIENT_ALIGNED_DATA"
    assert result["coverage"]["exact_timestamp_matches"] == 1


def test_combined_analysis_returns_insufficient_if_no_aligned_data(tmp_path):
    engine, _, ratios = build_engine(tmp_path)
    ratios.save("GLOBAL_LONG_SHORT", "BTCUSDT", "1h", [global_row(9000, 1.2)])
    result = engine.analyze("BTCUSDT", "1h", 10)
    assert result["status"] == "INSUFFICIENT_ALIGNED_DATA"
    assert result["coverage"]["exact_timestamp_matches"] == 0


def test_combined_analysis_validates_inputs(tmp_path):
    engine, _, _ = build_engine(tmp_path)
    with pytest.raises(ValueError, match="symbol"):
        engine.analyze("")
    with pytest.raises(ValueError, match="period"):
        engine.analyze("BTCUSDT", "2w")
    with pytest.raises(ValueError, match="limit"):
        engine.analyze("BTCUSDT", "1h", 1)
