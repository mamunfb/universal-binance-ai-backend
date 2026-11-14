import asyncio
import logging

import pytest

import app.services.liquidation_collector as liquidation_module
from app.services.liquidation_collector import (
    LiquidationCollector,
    LiquidationStore,
    normalize_force_order,
)


def sample_message():
    return {
        "e": "forceOrder",
        "E": 1700000000123,
        "st": 1,
        "o": {
            "s": "BTCUSDT",
            "ps": "BTCUSDT",
            "S": "SELL",
            "o": "LIMIT",
            "q": "0.02",
            "p": "50000",
            "ap": "49900",
            "X": "FILLED",
            "l": "0.02",
            "z": "0.02",
            "T": 1700000000100,
        },
    }


def test_normalize_force_order_and_notional():
    event = normalize_force_order(sample_message())
    assert event is not None
    assert event["symbol"] == "BTCUSDT"
    assert event["side"] == "SELL"
    assert event["approx_cumulative_notional"] == 998.0
    assert event["market_type"] == 1


@pytest.mark.parametrize("field,value", [
    ("ap", "NaN"),
    ("ap", "Infinity"),
    ("q", "-1"),
    ("l", "-0.1"),
    ("z", "Infinity"),
    ("E", -1),
    ("T", -1),
    ("s", ""),
    ("S", "HOLD"),
])
def test_invalid_force_order_is_ignored(field, value):
    message = sample_message()
    if field in {"E"}:
        message[field] = value
    elif field == "T":
        message["o"][field] = value
    else:
        message["o"][field] = value
    assert normalize_force_order(message) is None


def test_boolean_timestamp_and_non_object_message_are_rejected():
    message = sample_message()
    message["E"] = True
    assert normalize_force_order(message) is None
    assert normalize_force_order([]) is None


def test_store_persists_and_filters_events(tmp_path):
    store = LiquidationStore(str(tmp_path / "events.sqlite3"))
    event = normalize_force_order(sample_message())
    assert event is not None
    store.insert(event)
    assert store.count() == 1
    rows = store.recent("btcusdt", 10)
    assert len(rows) == 1
    assert rows[0]["symbol"] == "BTCUSDT"
    assert store.recent("ETHUSDT", 10) == []


def test_store_deduplicates_exact_repeated_payloads(tmp_path):
    store = LiquidationStore(str(tmp_path / "events.sqlite3"))
    event = normalize_force_order(sample_message())
    assert event is not None
    assert len(event["event_fingerprint"]) == 64

    store.insert(event)
    store.insert(event)

    assert store.count() == 1


def test_fingerprint_is_independent_of_json_object_key_order():
    message = sample_message()

    def reverse_mapping(value):
        if isinstance(value, dict):
            return {key: reverse_mapping(item) for key, item in reversed(list(value.items()))}
        if isinstance(value, list):
            return [reverse_mapping(item) for item in value]
        return value

    first = normalize_force_order(message)
    second = normalize_force_order(reverse_mapping(message))
    assert first is not None and second is not None
    assert first["event_fingerprint"] == second["event_fingerprint"]


def test_invalid_message_is_ignored():
    assert normalize_force_order({"e": "aggTrade"}) is None
    assert normalize_force_order({"e": "forceOrder", "o": []}) is None


def test_collector_status_and_logs_expose_only_exception_class(tmp_path, monkeypatch, caplog):
    class BrokenConnection:
        async def __aenter__(self):
            raise RuntimeError("sensitive provider detail")

        async def __aexit__(self, exc_type, exc, traceback):
            return False

    def fake_connect(*args, **kwargs):
        return BrokenConnection()

    async def cancel_retry(_delay):
        raise asyncio.CancelledError

    store = LiquidationStore(str(tmp_path / "safe-status.sqlite3"))
    collector = LiquidationCollector(store)
    monkeypatch.setattr(liquidation_module, "connect", fake_connect)
    monkeypatch.setattr(liquidation_module.asyncio, "sleep", cancel_retry)

    with caplog.at_level(logging.WARNING, logger=liquidation_module.__name__):
        with pytest.raises(asyncio.CancelledError):
            asyncio.run(collector.run())

    status = collector.status()
    assert status["last_error"] == "RuntimeError"
    assert "sensitive provider detail" not in str(status)
    assert "RuntimeError" in caplog.text
    assert "sensitive provider detail" not in caplog.text



def test_collector_status_remains_available_when_storage_count_fails():
    class UnavailableStore:
        def count(self):
            raise RuntimeError("sensitive database connection detail")

    collector = LiquidationCollector(UnavailableStore())
    status = collector.status()

    assert status["collector_enabled"] is True
    assert status["stored_event_count"] is None
    assert status["storage_status"] == "UNAVAILABLE"
    assert status["storage_error"] == "RuntimeError"
    assert "sensitive database connection detail" not in str(status)
