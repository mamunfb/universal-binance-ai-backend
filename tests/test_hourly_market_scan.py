from scripts.hourly_market_scan import summarize_status


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
