import pytest

from app.services.derivatives_ratio_store import DerivativesRatioStore


def global_row(timestamp=1700000000000, ratio="1.2", long="0.55", short="0.45"):
    return {
        "symbol": "BTCUSDT", "timestamp": timestamp,
        "longShortRatio": ratio, "longAccount": long, "shortAccount": short,
    }


def taker_row(timestamp=1700000000000, ratio="1.1", buy="100", sell="90"):
    return {
        "symbol": "BTCUSDT", "timestamp": timestamp,
        "buySellRatio": ratio, "buyVol": buy, "sellVol": sell,
    }


def test_global_long_short_ratio_store_round_trip_and_order(tmp_path):
    store = DerivativesRatioStore(str(tmp_path / "ratios.sqlite3"))
    result = store.save("GLOBAL_LONG_SHORT", "btcusdt", "1h", [
        global_row(1700003600000), global_row(),
    ])
    assert result["stored_count"] == 2
    history = store.history("GLOBAL_LONG_SHORT", "BTCUSDT", "1h")
    assert [r["timestamp_ms"] for r in history["records"]] == [
        1700000000000, 1700003600000
    ]
    assert history["records"][0]["long_short_ratio"] == 1.2
    assert "account counts" in history["interpretation_warning"].lower()


def test_taker_ratio_store_and_idempotent_upsert(tmp_path):
    store = DerivativesRatioStore(str(tmp_path / "ratios.sqlite3"))
    store.save("TAKER_BUY_SELL", "BTCUSDT", "5m", [taker_row()])
    result = store.save("TAKER_BUY_SELL", "BTCUSDT", "5m", [
        taker_row(ratio="1.3", buy="130", sell="100")
    ])
    history = store.history("TAKER_BUY_SELL", "BTCUSDT", "5m")
    assert result["total_stored_count"] == 1
    assert history["records"][0]["buy_sell_ratio"] == 1.3
    assert history["records"][0]["buy_volume"] == 130.0


@pytest.mark.parametrize("ratio_type,row", [
    ("GLOBAL_LONG_SHORT", global_row(ratio="nan")),
    ("GLOBAL_LONG_SHORT", global_row(long="-0.1")),
    ("TAKER_BUY_SELL", taker_row(buy="inf")),
    ("TAKER_BUY_SELL", taker_row(sell="-1")),
])
def test_ratio_store_rejects_invalid_metrics(tmp_path, ratio_type, row):
    store = DerivativesRatioStore(str(tmp_path / "ratios.sqlite3"))
    with pytest.raises(ValueError):
        store.save(ratio_type, "BTCUSDT", "1h", [row])
    assert store.history(ratio_type, "BTCUSDT", "1h")["returned_count"] == 0


def test_ratio_store_rejects_bad_symbol_duplicate_period_and_type(tmp_path):
    store = DerivativesRatioStore(str(tmp_path / "ratios.sqlite3"))
    with pytest.raises(ValueError, match="symbol"):
        store.save("GLOBAL_LONG_SHORT", "BTCUSDT", "1h", [global_row() | {"symbol": "ETHUSDT"}])
    with pytest.raises(ValueError, match="Duplicate"):
        store.save("GLOBAL_LONG_SHORT", "BTCUSDT", "1h", [global_row(), global_row()])
    with pytest.raises(ValueError, match="period"):
        store.save("GLOBAL_LONG_SHORT", "BTCUSDT", "2w", [global_row()])
    with pytest.raises(ValueError, match="ratio_type"):
        store.save("UNKNOWN", "BTCUSDT", "1h", [global_row()])


def test_ratio_store_history_filters_and_validates_bounds(tmp_path):
    store = DerivativesRatioStore(str(tmp_path / "ratios.sqlite3"))
    store.save("GLOBAL_LONG_SHORT", "BTCUSDT", "1h", [
        global_row(1000), global_row(2000), global_row(3000),
    ])
    result = store.history("GLOBAL_LONG_SHORT", "BTCUSDT", "1h", 1500, 2500)
    assert [row["timestamp_ms"] for row in result["records"]] == [2000]
    with pytest.raises(ValueError, match="end_time_ms"):
        store.history("GLOBAL_LONG_SHORT", "BTCUSDT", "1h", 2000, 1000)
