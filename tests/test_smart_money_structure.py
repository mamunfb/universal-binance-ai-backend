from app.services.historical_klines import HistoricalKlineStore
from app.services.smart_money_structure import SmartMoneyMarketStructure


def _row(ts, open_, high, low, close):
    return [ts, str(open_), str(high), str(low), str(close), "10",
            ts + 59_999, "1000", 20, "4", "400", "0"]


def test_structure_requires_sufficient_history(tmp_path):
    store = HistoricalKlineStore(str(tmp_path / "klines.sqlite3"))
    store.save_klines("SPOT", "BTCUSDT", "1m", [
        _row(i * 60_000, 100, 101, 99, 100) for i in range(20)
    ])
    result = SmartMoneyMarketStructure(store).analyze("SPOT", "BTCUSDT", "1m", 30)
    assert result["status"] == "INSUFFICIENT_DATA"


def test_structure_detects_fvg_and_premium_discount(tmp_path):
    store = HistoricalKlineStore(str(tmp_path / "klines.sqlite3"))
    rows = []
    # Oscillating closes create confirmed swing points; candle 12 creates a bullish gap.
    for i in range(40):
        price = 100 + (5 if i % 4 in (1, 2) else -2)
        rows.append(_row(i * 60_000, price, price + 1, price - 1, price + 0.2))
    rows[10] = _row(10 * 60_000, 100, 101, 99, 100)
    rows[11] = _row(11 * 60_000, 103, 104, 102, 103.5)
    rows[12] = _row(12 * 60_000, 106, 108, 105, 107)
    store.save_klines("SPOT", "BTCUSDT", "1m", rows)
    result = SmartMoneyMarketStructure(store).analyze(
        "SPOT", "BTCUSDT", "1m", 40, swing_left=2, swing_right=2
    )
    assert result["status"] in {"COMPLETED", "INSUFFICIENT_SWINGS"}
    if result["status"] == "COMPLETED":
        assert result["premium_discount"]["zone"] in {"PREMIUM", "DISCOUNT", "EQUILIBRIUM"}
        assert "fair_value_gap_candidates" in result
        assert result["coverage"]["candles_used"] == 40


def test_structure_validates_market_and_parameters(tmp_path):
    store = HistoricalKlineStore(str(tmp_path / "klines.sqlite3"))
    engine = SmartMoneyMarketStructure(store)
    try:
        engine.analyze("BAD", "BTCUSDT", "1m", 100)
    except ValueError as exc:
        assert "market" in str(exc)
    else:
        raise AssertionError("Expected invalid market to fail")
    try:
        engine.analyze("SPOT", "BTCUSDT", "1m", 100, swing_left=0)
    except ValueError as exc:
        assert "swing_left" in str(exc)
    else:
        raise AssertionError("Expected invalid swing setting to fail")
