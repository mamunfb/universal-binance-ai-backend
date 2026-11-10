from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.signal_lifecycle import build_signal_lifecycle


client = TestClient(app)


def test_signal_lifecycle_creates_bst_signal_id_and_validates_window():
    result = build_signal_lifecycle(
        symbol="BTCUSDT", market="SPOT", direction="LONG",
        driver_timeframe="15m", analysis_timestamp="2026-11-10T00:00:00Z",
        entry_window_start="2026-11-10T01:00:00Z",
        entry_window_end="2026-11-10T02:00:00Z",
        now=datetime(2026, 11, 10, 0, 30, tzinfo=timezone.utc),
    )
    assert result["signal_id"] == "BTCUSDT-SPOT-LONG-20261110-0600"
    assert result["maximum_signal_life_hours"] == 4
    assert result["status"] == "WAIT"
    assert result["decision_cap"] == "WAIT"
    assert result["entry_window_start_bst"].startswith("2026-11-10T07:00:00")


def test_signal_lifecycle_does_not_invent_entry_window():
    result = build_signal_lifecycle(
        symbol="ETHUSDT", market="USD_M", direction="SHORT",
        driver_timeframe="1h", analysis_timestamp="2026-11-10T00:00:00+00:00",
    )
    assert result["status"] == "TIMING_NOT_ESTABLISHED"
    assert result["entry_window_start_bst"] is None
    assert result["decision_cap"] == "WAIT"


def test_signal_lifecycle_rejects_window_beyond_signal_life():
    with pytest.raises(ValueError, match="must not exceed"):
        build_signal_lifecycle(
            symbol="BTCUSDT", market="USD_M", direction="LONG",
            driver_timeframe="5m", analysis_timestamp="2026-11-10T00:00:00Z",
            entry_window_start="2026-11-10T01:00:00Z",
            entry_window_end="2026-11-10T05:00:00Z",
        )


def test_signal_lifecycle_marks_expired_window():
    result = build_signal_lifecycle(
        symbol="BTCUSDT", market="USD_M", direction="SHORT",
        driver_timeframe="1h", analysis_timestamp="2026-11-10T00:00:00Z",
        entry_window_start="2026-11-10T01:00:00Z",
        entry_window_end="2026-11-10T02:00:00Z",
        now=datetime(2026, 11, 10, 3, 0, tzinfo=timezone.utc),
    )
    assert result["status"] == "EXPIRED"
    assert result["decision_cap"] == "NO_TRADE"


def test_signal_lifecycle_rejects_spot_short():
    with pytest.raises(ValueError, match="SPOT supports LONG only"):
        build_signal_lifecycle(
            symbol="BTCUSDT", market="SPOT", direction="SHORT",
            driver_timeframe="1h", analysis_timestamp="2026-11-10T00:00:00Z",
        )


def test_signal_lifecycle_api_returns_bst_timing_metadata():
    response = client.post("/api/v1/analysis/signal-lifecycle", json={
        "symbol": "BTCUSDT", "market": "SPOT", "direction": "LONG",
        "driver_timeframe": "4h", "analysis_timestamp": "2026-11-10T00:00:00Z",
    })
    assert response.status_code == 200
    assert response.json()["status"] == "TIMING_NOT_ESTABLISHED"
