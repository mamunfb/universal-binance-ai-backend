import pytest

from app.services.market_confluence_store import MarketConfluenceStore


def valid_payload():
    return {
        "market": "USD_M",
        "symbol": "BTCUSDT",
        "interval": "1h",
        "analyzed_at_ms": 1000,
        "confluence": {
            "bias": "BULLISH",
            "alignment": "BULLISH_EVIDENCE_ALIGNMENT",
        },
        "reference": {"price": 100.0, "close_time_ms": 999},
        "evidence": [{"source": "TEST"}],
    }


def test_snapshot_save_is_idempotent(tmp_path):
    store = MarketConfluenceStore(str(tmp_path / "snapshots.sqlite3"))
    payload = valid_payload()

    first = store.save(payload)
    second = store.save(payload)

    assert first["snapshot_id"] == second["snapshot_id"]
    assert store.history("USD_M", "BTCUSDT", "1h")["returned_count"] == 1


def test_future_reference_candle_is_rejected(tmp_path):
    store = MarketConfluenceStore(str(tmp_path / "snapshots.sqlite3"))
    payload = valid_payload()
    payload["reference"]["close_time_ms"] = 1001

    with pytest.raises(ValueError, match="fully closed"):
        store.save(payload)


@pytest.mark.parametrize(
    "field,value",
    [
        ("analyzed_at_ms", True),
        ("analyzed_at_ms", 1000.5),
        ("reference_price", True),
        ("reference_close_time_ms", False),
        ("reference_close_time_ms", 999.5),
    ],
)
def test_snapshot_rejects_boolean_and_fractional_numeric_fields(
    tmp_path, field, value
):
    store = MarketConfluenceStore(str(tmp_path / "snapshots.sqlite3"))
    payload = valid_payload()
    if field == "analyzed_at_ms":
        payload[field] = value
    elif field == "reference_price":
        payload["reference"]["price"] = value
    else:
        payload["reference"]["close_time_ms"] = value

    with pytest.raises(ValueError):
        store.save(payload)
    assert store.history("USD_M", "BTCUSDT", "1h")["returned_count"] == 0
