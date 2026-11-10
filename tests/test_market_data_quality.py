from app.services.historical_klines import HistoricalKlineStore
from app.services.market_data_quality import MarketDataQualityEngine


def candle(open_time, interval_ms=60_000):
    return [
        open_time, "100", "105", "99", "101", "10",
        open_time + interval_ms - 1, "1000", 25, "4", "400", "0",
    ]


def engine(tmp_path):
    return MarketDataQualityEngine(*[
        str(tmp_path / name) for name in (
            "klines.sqlite3", "funding.sqlite3", "oi.sqlite3",
            "ratios.sqlite3", "trades.sqlite3", "book.sqlite3",
        )
    ])


def test_quality_reports_no_data_without_claiming_health(tmp_path):
    result = engine(tmp_path).inspect(
        "SPOT", "BTCUSDT", "1m", lookback_hours=1, now_ms=1_700_000_100_000
    )
    assert result["status"] == "COMPLETED"
    assert result["sources"]["historical_klines"]["status"] == "NO_DATA"
    assert result["sources"]["aggregate_trades"]["status"] == "NO_DATA"
    assert result["sources"]["order_book_samples"]["continuity"] == "NOT_MEASURABLE"


def test_quality_detects_recent_candle_gaps_and_freshness(tmp_path):
    db = str(tmp_path / "klines.sqlite3")
    store = HistoricalKlineStore(db)
    start = 1_700_000_040_000
    store.save_klines("SPOT", "BTCUSDT", "1m", [
        candle(start), candle(start + 2 * 60_000),
    ])
    now = start + 2 * 60_000 + 30_000
    result = engine(tmp_path).inspect(
        "SPOT", "BTCUSDT", "1m", lookback_hours=1, now_ms=now
    )
    source = result["sources"]["historical_klines"]
    assert source["freshness"] == "FRESH"
    assert source["status"] == "DEGRADED"
    assert source["coverage"]["coverage"]["missing_candle_count"] > 0


def test_quality_marks_old_candles_stale(tmp_path):
    db = str(tmp_path / "klines.sqlite3")
    store = HistoricalKlineStore(db)
    start = 1_700_000_040_000
    store.save_klines("SPOT", "BTCUSDT", "1m", [candle(start)])
    now = start + 10 * 60_000
    result = engine(tmp_path).inspect(
        "SPOT", "BTCUSDT", "1m", lookback_hours=1, now_ms=now
    )
    source = result["sources"]["historical_klines"]
    assert source["freshness"] == "STALE"
    assert source["status"] == "STALE"


def test_stream_freshness_does_not_claim_gap_free_continuity(tmp_path):
    from app.services.aggregate_trade_stream import AggregateTradeStore
    db = str(tmp_path / "trades.sqlite3")
    store = AggregateTradeStore(db)
    store.insert({
        "market": "SPOT", "symbol": "BTCUSDT", "trade_id": 1,
        "event_time_ms": 1_700_000_000_000, "trade_time_ms": 1_700_000_000_000,
        "price": 100.0, "quantity": 1.0, "notional": 100.0,
        "buyer_is_maker": False, "aggressor_side": "BUY", "raw_json": "{}",
    })
    result = engine(tmp_path).inspect(
        "SPOT", "BTCUSDT", "1h", lookback_hours=24, now_ms=1_700_000_001_000
    )
    source = result["sources"]["aggregate_trades"]
    assert source["status"] == "NOT_MEASURABLE"
    assert source["freshness"] == "FRESH"
    assert source["continuity"] == "NOT_MEASURABLE"

def test_database_schema_error_is_unknown_not_no_data(tmp_path):
    broken_db = tmp_path / "broken.sqlite3"
    broken_db.write_text("not a sqlite database")
    result = MarketDataQualityEngine(
        str(broken_db), str(tmp_path / "funding.sqlite3"),
        str(tmp_path / "oi.sqlite3"), str(tmp_path / "ratios.sqlite3"),
        str(tmp_path / "trades.sqlite3"), str(tmp_path / "book.sqlite3"),
    ).inspect("SPOT", "BTCUSDT", "1m", lookback_hours=1, now_ms=1_700_000_100_000)
    assert result["sources"]["historical_klines"]["status"] == "UNKNOWN"
    assert result["sources"]["historical_klines"]["freshness"] == "UNKNOWN"
