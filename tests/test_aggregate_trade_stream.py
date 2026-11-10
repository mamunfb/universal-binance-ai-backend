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
    result = store.recent("SPOT", "BTCUSDT", 10, 100, 200)
    assert len(result) == 1
    assert result[0]["buyer_is_maker"] is False
    assert store.recent("USD_M", "BTCUSDT") == []


def test_aggregate_trade_stream_urls():
    assert "stream.binance.com:9443/ws/btcusdt@aggTrade" == aggregate_trade_stream_url("SPOT", "BTCUSDT")
    assert "fstream.binance.com/market/ws/btcusdt@aggTrade" == aggregate_trade_stream_url("USD_M", "BTCUSDT")
    assert "dstream.binance.com/ws/btcusd_perp@aggTrade" == aggregate_trade_stream_url("COIN_M", "BTCUSD_PERP")
