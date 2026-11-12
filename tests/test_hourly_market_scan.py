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
