from app.services.funding_open_interest_analysis import FundingOpenInterestAnalysis
from app.services.funding_rates import FundingRateStore
from app.services.historical_klines import HistoricalKlineStore
from app.services.open_interest import OpenInterestStore


def test_combined_analysis_reports_price_oi_and_funding_context(tmp_path):
    funding = FundingRateStore(str(tmp_path / "funding.sqlite3"))
    oi = OpenInterestStore(str(tmp_path / "oi.sqlite3"))
    klines = HistoricalKlineStore(str(tmp_path / "klines.sqlite3"))
    start = 1700000000000
    oi.save("USD_M", "BTCUSDT", "1h", [
        {"symbol": "BTCUSDT", "timestamp": start, "sumOpenInterest": "100",
         "sumOpenInterestValue": "5000000"},
        {"symbol": "BTCUSDT", "timestamp": start + 3600000, "sumOpenInterest": "110",
         "sumOpenInterestValue": "5500000"},
        {"symbol": "BTCUSDT", "timestamp": start + 7200000, "sumOpenInterest": "120",
         "sumOpenInterestValue": "6000000"},
    ])
    funding.save("USD_M", "BTCUSDT", [
        {"symbol": "BTCUSDT", "fundingTime": start + 3600000,
         "fundingRate": "0.0002", "markPrice": "51000"},
        {"symbol": "BTCUSDT", "fundingTime": start + 7200000,
         "fundingRate": "0.0001", "markPrice": "52000"},
    ])
    klines.save_klines("USD_M", "BTCUSDT", "1h", [
        [start, "50000", "51000", "49000", "50500", "10",
         start + 3599999, "500000", 100, "5", "250000"],
        [start + 3600000, "50500", "52000", "50000", "51500", "12",
         start + 7199999, "600000", 120, "6", "300000"],
        [start + 7200000, "51500", "53000", "51000", "52500", "13",
         start + 10799999, "650000", 130, "7", "350000"],
    ])

    result = FundingOpenInterestAnalysis(funding, oi, klines).analyze(
        "btcusdt", "1h", "1h", 24
    )
    assert result["status"] == "COMPLETED"
    assert result["metrics"]["open_interest"]["change_percent"] == 20.0
    assert result["metrics"]["price"]["direction"] == "UP"
    assert result["metrics"]["funding"]["bias"] == "POSITIVE_FUNDING_LONGS_PAY_SHORTS"
    assert result["interpretation"]["code"] == "PRICE_UP_WITH_OI_UP_POSITION_BUILDUP_CANDIDATE"
    assert "does not identify" in result["interpretation"]["summary"]
    assert result["window"]["funding_events"] == 2


def test_combined_analysis_does_not_infer_price_or_direction_from_oi_alone(tmp_path):
    funding = FundingRateStore(str(tmp_path / "funding.sqlite3"))
    oi = OpenInterestStore(str(tmp_path / "oi.sqlite3"))
    klines = HistoricalKlineStore(str(tmp_path / "klines.sqlite3"))
    start = 1700000000000
    oi.save("USD_M", "BTCUSDT", "1h", [
        {"symbol": "BTCUSDT", "timestamp": start, "sumOpenInterest": "100",
         "sumOpenInterestValue": "5000000"},
        {"symbol": "BTCUSDT", "timestamp": start + 3600000, "sumOpenInterest": "120",
         "sumOpenInterestValue": "6000000"},
    ])
    result = FundingOpenInterestAnalysis(funding, oi, klines).analyze("BTCUSDT")
    assert result["status"] == "COMPLETED"
    assert result["metrics"]["price"]["direction"] == "UNAVAILABLE"
    assert result["interpretation"]["code"] == "PRICE_CONTEXT_UNAVAILABLE"
    assert result["metrics"]["funding"]["bias"] == "UNAVAILABLE"


def test_combined_analysis_requires_two_open_interest_records(tmp_path):
    result = FundingOpenInterestAnalysis(
        FundingRateStore(str(tmp_path / "f.sqlite3")),
        OpenInterestStore(str(tmp_path / "o.sqlite3")),
        HistoricalKlineStore(str(tmp_path / "k.sqlite3")),
    ).analyze("BTCUSDT")
    assert result["status"] == "INSUFFICIENT_DATA"
    assert result["analysis"] is None
