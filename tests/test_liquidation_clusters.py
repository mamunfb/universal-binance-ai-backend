from app.services.liquidation_collector import LiquidationStore
from app.services.liquidation_clusters import LiquidationClusterAnalysis


def _event(ts, side, price, qty):
    return {
        "event_time_ms": ts, "trade_time_ms": ts, "symbol": "BTCUSDT",
        "pair_symbol": "BTCUSDT", "market_type": 1, "side": side,
        "order_type": "LIMIT", "status": "FILLED", "average_price": price,
        "original_quantity": qty, "last_filled_quantity": qty,
        "cumulative_filled_quantity": qty,
        "approx_cumulative_notional": price * qty, "raw_json": "{}",
    }


def test_liquidation_clusters_group_prices_and_sides(tmp_path):
    store = LiquidationStore(str(tmp_path / "liq.sqlite3"))
    store.insert(_event(1000, "SELL", 60000, 0.1))
    store.insert(_event(2000, "SELL", 60010, 0.2))
    store.insert(_event(3000, "BUY", 61000, 0.1))
    result = LiquidationClusterAnalysis(store).analyze("BTCUSDT", limit=100)
    assert result["status"] == "COMPLETED"
    assert result["coverage"]["events_usable"] == 3
    assert len(result["clusters"]) == 2
    first = result["clusters"][0]
    assert first["event_count"] == 2
    assert first["sell_side_events"] == 2
    assert first["approx_notional"] == 18002.0


def test_liquidation_clusters_filter_time_and_min_events(tmp_path):
    store = LiquidationStore(str(tmp_path / "liq.sqlite3"))
    store.insert(_event(1000, "SELL", 60000, 0.1))
    store.insert(_event(2000, "BUY", 61000, 0.1))
    result = LiquidationClusterAnalysis(store).analyze(
        "BTCUSDT", start_time_ms=1500, end_time_ms=2500, min_events=2
    )
    assert result["status"] == "NO_CLUSTERS"
    assert result["coverage"]["events_examined"] == 1


def test_liquidation_clusters_report_no_data_and_validate(tmp_path):
    store = LiquidationStore(str(tmp_path / "liq.sqlite3"))
    engine = LiquidationClusterAnalysis(store)
    assert engine.analyze("BTCUSDT")["status"] == "NO_STORED_DATA"
    try:
        engine.analyze("BTCUSDT", bucket_bps=0)
    except ValueError as exc:
        assert "bucket_bps" in str(exc)
    else:
        raise AssertionError("Expected invalid bucket width")
