import pytest

from app.services.liquidation_collector import LiquidationStore, normalize_force_order


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
