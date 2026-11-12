import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.hourly_market_scan import collection_succeeded, summarize_status


def test_summarize_status_requires_all_three_market_scans_to_complete():
    results = {
        "SPOT": {"status": "COMPLETED"},
        "USD_M": {"status": "COMPLETED"},
        "COIN_M": {"status": "COMPLETED"},
    }
    assert summarize_status(results) == "COMPLETED"


def test_summarize_status_marks_partial_market_failure():
    results = {
        "SPOT": {"status": "COMPLETED"},
        "USD_M": {"status": "FAILED"},
        "COIN_M": {"status": "COMPLETED"},
    }
    assert summarize_status(results) == "FAILED"


def test_summarize_status_marks_incomplete_market_data():
    results = {
        "SPOT": {"status": "COMPLETED"},
        "USD_M": {"status": "INCOMPLETE"},
        "COIN_M": {"status": "COMPLETED"},
    }
    assert summarize_status(results) == "INCOMPLETE"


def test_summarize_status_respects_incomplete_research_phase():
    results = {
        "SPOT": {"status": "COMPLETED", "phase_status": "INCOMPLETE"},
        "USD_M": {"status": "COMPLETED", "phase_status": "INCOMPLETE"},
        "COIN_M": {"status": "COMPLETED", "phase_status": "INCOMPLETE"},
    }
    assert summarize_status(results) == "INCOMPLETE"



def test_collection_succeeds_when_market_data_collected_but_research_phase_is_incomplete():
    results = {
        "SPOT": {"status": "COMPLETED", "phase_status": "INCOMPLETE"},
        "USD_M": {"status": "COMPLETED", "phase_status": "INCOMPLETE"},
        "COIN_M": {"status": "COMPLETED", "phase_status": "INCOMPLETE"},
    }
    assert collection_succeeded(results) is True
    assert summarize_status(results) == "INCOMPLETE"


def test_collection_fails_when_any_market_scan_failed():
    results = {
        "SPOT": {"status": "COMPLETED"},
        "USD_M": {"status": "FAILED"},
        "COIN_M": {"status": "COMPLETED"},
    }
    assert collection_succeeded(results) is False


async def test_spot_provider_initialization_failure_does_not_skip_futures(monkeypatch):
    import scripts.hourly_market_scan as scanner

    attempted_markets = []

    def broken_spot_provider(*args, **kwargs):
        raise RuntimeError("invalid Spot configuration")

    class FakeFuturesProvider:
        def __init__(self, market, timeout_seconds):
            self.market = market
            attempted_markets.append(market)

    async def fake_futures_scan(provider):
        return {"status": "COMPLETED", "market": provider.market}

    monkeypatch.setattr(scanner, "BinanceSpotProvider", broken_spot_provider)
    monkeypatch.setattr(scanner, "BinanceFuturesProvider", FakeFuturesProvider)
    monkeypatch.setattr(scanner, "scan_futures_markets", fake_futures_scan)

    results = await scanner.collect_market_scans()

    assert results["SPOT"]["status"] == "FAILED"
    assert results["SPOT"]["error_type"] == "RuntimeError"
    assert attempted_markets == ["USD_M", "COIN_M"]
    assert results["USD_M"]["status"] == "COMPLETED"
    assert results["COIN_M"]["status"] == "COMPLETED"
