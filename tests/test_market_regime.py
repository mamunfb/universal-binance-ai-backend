from app.services.historical_klines import HistoricalKlineStore
from app.services.market_regime import MarketRegimeAnalysis


def _row(ts, open_, high, low, close):
    return [ts, str(open_), str(high), str(low), str(close), "10",
            ts + 59_999, "1000", 20, "4", "400", "0"]


def test_market_regime_requires_sufficient_history(tmp_path):
    store = HistoricalKlineStore(str(tmp_path / "klines.sqlite3"))
    rows = [_row(i * 60_000, 100, 101, 99, 100 + i * 0.01) for i in range(39)]
    store.save_klines("SPOT", "BTCUSDT", "1m", rows)
    result = MarketRegimeAnalysis(store).analyze("SPOT", "BTCUSDT", "1m", 100)
    assert result["status"] == "INSUFFICIENT_DATA"
    assert result["market_regime"] == "UNKNOWN"


def test_market_regime_returns_metrics_for_sufficient_history(tmp_path):
    store = HistoricalKlineStore(str(tmp_path / "klines.sqlite3"))
    rows = []
    price = 100.0
    for i in range(80):
        next_price = price + (0.15 if i % 2 == 0 else -0.10)
        rows.append(_row(i * 60_000, price, max(price, next_price) + 0.1,
                         min(price, next_price) - 0.1, next_price))
        price = next_price
    store.save_klines("SPOT", "BTCUSDT", "1m", rows)
    result = MarketRegimeAnalysis(store).analyze("SPOT", "BTCUSDT", "1m", 100)
    assert result["status"] == "COMPLETED"
    assert result["volatility_regime"] in {
        "HIGH_VOLATILITY", "LOW_VOLATILITY", "NORMAL_VOLATILITY", "UNKNOWN"
    }
    assert result["structure_regime"] in {"TREND", "RANGE"}
    assert 0 <= result["metrics"]["20_candle_path_efficiency"] <= 1
    assert result["limitations"]


def test_market_regime_rejects_bad_parameters(tmp_path):
    store = HistoricalKlineStore(str(tmp_path / "klines.sqlite3"))
    engine = MarketRegimeAnalysis(store)
    try:
        engine.analyze("BAD", "BTCUSDT", "1m", 100)
    except ValueError as exc:
        assert "market" in str(exc)
    else:
        raise AssertionError("Expected invalid market to fail")
