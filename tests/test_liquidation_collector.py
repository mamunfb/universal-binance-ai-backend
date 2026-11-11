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


def test_invalid_message_is_ignored():
    assert normalize_force_order({"e": "aggTrade"}) is None
    assert normalize_force_order({"e": "forceOrder", "o": []}) is None



def test_invalid_or_non_finite_force_order_quantities_are_ignored():
    import copy

    cases = (
        ("q", "not-a-number"),
        ("l", "not-a-number"),
        ("ap", "NaN"),
        ("z", "Infinity"),
        ("q", "-0.1"),
        ("l", "-0.1"),
    )
    for field, value in cases:
        message = copy.deepcopy(sample_message())
        message["o"][field] = value
        assert normalize_force_order(message) is None


def test_negative_force_order_timestamps_are_ignored():
    import copy

    message = copy.deepcopy(sample_message())
    message["E"] = -1
    assert normalize_force_order(message) is None

    message = copy.deepcopy(sample_message())
    message["o"]["T"] = -1
    assert normalize_force_order(message) is None
