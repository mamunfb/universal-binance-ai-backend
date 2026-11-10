import pytest

from app.services.multi_timeframe_derivatives import MultiTimeframeDerivativesAnalysis


class FakeEngine:
    def __init__(self, endings=None, missing=None, directions=None):
        self.endings = endings or {}
        self.missing = missing or set()
        self.directions = directions or {}
        self.calls = []

    def analyze(self, symbol, period, price_interval, limit):
        self.calls.append((symbol, period, price_interval, limit))
        if period in self.missing:
            return {"status": "INSUFFICIENT_DATA", "period": period}
        return {
            "status": "COMPLETED",
            "period": period,
            "window": {"end_time_ms": self.endings.get(period, 1000)},
            "trend": {"direction": self.directions.get(period, "OI_RISING")},
        }


def test_aligned_timeframes_report_agreement():
    engine = FakeEngine()
    result = MultiTimeframeDerivativesAnalysis(engine).analyze(
        "btcusdt", ["5m", "1h"], 24
    )
    assert result["status"] == "COMPLETED"
    assert result["timeframe_agreement"]["classification"] == "ALL_OI_RISING"
    assert result["timeframe_agreement"]["end_timestamps_identical"] is True
    assert engine.calls == [
        ("BTCUSDT", "5m", "5m", 24),
        ("BTCUSDT", "1h", "1h", 24),
    ]


def test_unaligned_timestamps_withhold_confirmation():
    engine = FakeEngine(endings={"5m": 1000, "1h": 2000})
    result = MultiTimeframeDerivativesAnalysis(engine).analyze(
        "BTCUSDT", ["5m", "1h"]
    )
    assert result["status"] == "COMPLETED"
    assert result["timeframe_agreement"]["classification"] == "UNALIGNED_END_TIMESTAMPS"


def test_missing_timeframe_withholds_confirmation():
    engine = FakeEngine(missing={"1h"})
    result = MultiTimeframeDerivativesAnalysis(engine).analyze(
        "BTCUSDT", ["5m", "1h"]
    )
    assert result["status"] == "INCOMPLETE"
    assert result["missing_periods"] == ["1h"]
    assert result["timeframe_agreement"]["classification"] == "INCOMPLETE_COVERAGE"


def test_all_missing_reports_insufficient_data():
    engine = FakeEngine(missing={"5m", "1h"})
    result = MultiTimeframeDerivativesAnalysis(engine).analyze(
        "BTCUSDT", ["5m", "1h"]
    )
    assert result["status"] == "INSUFFICIENT_DATA"
    assert result["timeframe_agreement"]["classification"] == "UNAVAILABLE"


def test_mixed_directions_report_mixed():
    engine = FakeEngine(directions={"5m": "OI_RISING", "1h": "OI_FALLING"})
    result = MultiTimeframeDerivativesAnalysis(engine).analyze(
        "BTCUSDT", ["5m", "1h"]
    )
    assert result["timeframe_agreement"]["classification"] == "MIXED_OI_DIRECTIONS"


@pytest.mark.parametrize("periods", [[], ["1m"], ["1h", "1h"], ["5m"] * 10])
def test_invalid_periods_rejected(periods):
    with pytest.raises(ValueError):
        MultiTimeframeDerivativesAnalysis(FakeEngine()).analyze("BTCUSDT", periods)


def test_single_timeframe_does_not_claim_confirmation():
    result = MultiTimeframeDerivativesAnalysis(FakeEngine()).analyze("BTCUSDT", ["1h"])
    assert result["timeframe_agreement"]["classification"] == "SINGLE_TIMEFRAME_ONLY"
