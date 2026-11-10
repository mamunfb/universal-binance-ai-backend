from app.services.market_confluence_performance import MarketConfluencePerformance


class SnapshotStore:
    def __init__(self, snapshots):
        self.snapshots = snapshots

    def history(self, market, symbol, interval, limit):
        return {"returned_count": len(self.snapshots), "snapshots": self.snapshots}


class KlineStore:
    def history(self, market, symbol, interval, start_time_ms, end_time_ms, limit):
        target = end_time_ms - 3_600_000
        if self.empty:
            return {"candles": []}
        return {"candles": [{
            "open_time_ms": start_time_ms,
            "close_time_ms": target,
            "high": 110.0,
            "low": 90.0,
            "close": 105.0,
        }]}

    empty = False


def snapshot(bias):
    return {
        "snapshot_id": bias,
        "analyzed_at_ms": 1_000_000,
        "bias": bias,
        "alignment": "TEST",
        "reference_price": 100.0,
    }


def test_directional_outcomes_and_mixed_exclusion():
    evaluator = MarketConfluencePerformance(
        SnapshotStore([snapshot("BULLISH"), snapshot("BEARISH"), snapshot("MIXED")]),
        KlineStore(),
    )
    result = evaluator.evaluate("USD_M", "BTCUSDT", "1h", "1m", 10)
    one_hour = result["horizons"]["1"]
    assert one_hour["sample_size"] == 3
    assert one_hour["directional_sample_size"] == 2
    assert one_hour["directional_positive_fraction"] == 0.5
    assert one_hour["outcomes"][0]["directional_return_percent"] == 5.0
    assert one_hour["outcomes"][1]["directional_return_percent"] == -5.0
    assert one_hour["outcomes"][2]["directional_return_percent"] is None


def test_missing_future_candles_remain_pending():
    klines = KlineStore()
    klines.empty = True
    evaluator = MarketConfluencePerformance(SnapshotStore([snapshot("BULLISH")]), klines)
    result = evaluator.evaluate("USD_M", "BTCUSDT", "1h", "1m", 10)
    assert result["horizons"]["1"]["status"] == "INSUFFICIENT_FUTURE_DATA"
    assert result["horizons"]["1"]["pending_or_not_matured"] == 1
    assert result["horizons"]["1"]["directional_positive_fraction"] is None
