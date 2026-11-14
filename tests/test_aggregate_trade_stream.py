from app.services.aggregate_trade_stream import (
    AggregateTradeStore, aggregate_trade_stream_url, normalize_aggregate_trade,
)


def sample_trade():
    return {
        "e": "aggTrade", "E": 1700000000123, "s": "BTCUSDT", "a": 123,
        "p": "50000", "q": "0.02", "f": 10, "l": 11,
        "T": 1700000000100, "m": False,
    }


def test_aggregate_trade_normalization_and_taker_side():
    buy = normalize_aggregate_trade(sample_trade(), "SPOT")
    assert buy is not None
    assert buy["aggressor_side"] == "BUY"
    assert buy["notional"] == 1000
    payload = sample_trade()
    payload["m"] = True
    sell = normalize_aggregate_trade(payload, "USD_M")
    assert sell is not None
    assert sell["aggressor_side"] == "SELL"
    assert normalize_aggregate_trade({"e": "depthUpdate"}, "SPOT") is None


def test_aggregate_trade_store_is_idempotent_and_filters(tmp_path):
    store = AggregateTradeStore(str(tmp_path / "trades.sqlite3"))
    row = normalize_aggregate_trade(sample_trade(), "SPOT")
    assert row is not None
    store.insert(row)
    store.insert(row)
    assert store.count() == 1
    result = store.recent("SPOT", "BTCUSDT", 10, 1_700_000_000_000, 1_700_000_001_000)
    assert len(result) == 1
    assert result[0]["buyer_is_maker"] is False
    assert store.recent("USD_M", "BTCUSDT") == []


def test_aggregate_trade_store_rejects_lease_with_sqlite_storage(tmp_path):
    import pytest

    store = AggregateTradeStore(str(tmp_path / "trades.sqlite3"))
    row = normalize_aggregate_trade(sample_trade(), "SPOT")
    assert row is not None
    with pytest.raises(ValueError, match="PostgreSQL"):
        store.insert(row, lease=object())


def test_aggregate_trade_stream_urls():
    assert "wss://stream.binance.com:9443/ws/btcusdt@aggTrade" == aggregate_trade_stream_url("SPOT", "BTCUSDT")
    assert "wss://fstream.binance.com/market/ws/btcusdt@aggTrade" == aggregate_trade_stream_url("USD_M", "BTCUSDT")
    assert "wss://dstream.binance.com/ws/btcusd_perp@aggTrade" == aggregate_trade_stream_url("COIN_M", "BTCUSD_PERP")


def test_aggregate_trade_normalization_rejects_invalid_database_values():
    invalid_cases = [
        ("SPOT", {"a": -1}),
        ("SPOT", {"E": -1}),
        ("SPOT", {"T": -1}),
        ("UNKNOWN", {}),
        ("SPOT", {"p": "nan"}),
        ("SPOT", {"q": "inf"}),
        ("SPOT", {"p": "1e308", "q": "1e308"}),
        ("SPOT", {"a": True}),
        ("SPOT", {"E": False}),
    ]
    for market, changes in invalid_cases:
        payload = sample_trade()
        payload.update(changes)
        assert normalize_aggregate_trade(payload, market) is None


def test_aggregate_trade_normalization_trims_symbol_and_rejects_empty_symbol():
    payload = sample_trade()
    payload["s"] = "  btcusdt  "
    normalized = normalize_aggregate_trade(payload, "spot")
    assert normalized is not None
    assert normalized["symbol"] == "BTCUSDT"

    payload["s"] = "   "
    assert normalize_aggregate_trade(payload, "SPOT") is None
