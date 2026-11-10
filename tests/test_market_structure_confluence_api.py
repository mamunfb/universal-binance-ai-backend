from fastapi.testclient import TestClient

from app import main
from app.main import app

client = TestClient(app)


def _candles():
    return [{
        "open_time_ms": i * 60_000, "close_time_ms": i * 60_000 + 59_999,
        "open": 100.0, "high": 102.0, "low": 98.0, "close": 100.0,
    } for i in range(45)]


def test_market_structure_confluence_api_combines_local_analyses(monkeypatch):
    candles = _candles()

    class KlineStore:
        def history(self, market, symbol, interval, start_time_ms=None, end_time_ms=None, limit=1000):
            return {"candles": candles, "coverage": {"gaps": []}}

    class TradeStore:
        def recent(self, market, symbol, limit, start_time_ms=None, end_time_ms=None):
            return []

    class BookStore:
        def recent(self, market, symbol, limit, start_time_ms=None, end_time_ms=None):
            return []

    class Structure:
        def __init__(self, store):
            pass

        def analyze(self, *args):
            return {"status": "COMPLETED", "structure": "BULLISH",
                    "structure_break": {"type": "BOS", "direction": "BULLISH",
                                        "confirmed_by_close": True}}

    class Regime:
        def __init__(self, store):
            pass

        def analyze(self, *args):
            return {"status": "COMPLETED", "market_regime": "TREND",
                    "directional_context": "UP"}

    monkeypatch.setattr(main, "historical_kline_store", KlineStore())
    monkeypatch.setattr(main, "aggregate_trade_store", TradeStore())
    monkeypatch.setattr(main, "order_book_history_store", BookStore())
    monkeypatch.setattr(main, "SmartMoneyMarketStructure", Structure)
    monkeypatch.setattr(main, "MarketRegimeAnalysis", Regime)
    monkeypatch.setattr(main, "analyze_order_flow", lambda *args: {
        "status": "INSUFFICIENT_DATA", "trade_count": 0,
    })
    monkeypatch.setattr(main, "analyze_multi_timeframe_order_flow", lambda *args: {
        "status": "INSUFFICIENT_DATA", "cvd_agreement": "INSUFFICIENT_TIMEFRAME_DATA",
    })
    monkeypatch.setattr(main, "analyze_liquidity_sweep_confirmation", lambda *args: {
        "status": "NO_RECENT_SWEEP_CANDIDATE", "sweep_candidates": [],
    })

    response = client.get(
        "/api/v1/analysis/market-structure-confluence/SPOT/BTCUSDT",
        params={"interval": "1h", "limit": 100, "periods": "15m,1h,4h"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["confluence"]["bias"] == "BULLISH"
    assert payload["confluence"]["alignment"] == "BULLISH_EVIDENCE_ALIGNMENT"
    assert payload["coverage"]["local_history_only"] is True


def test_market_structure_confluence_api_rejects_duplicate_periods():
    response = client.get(
        "/api/v1/analysis/market-structure-confluence/SPOT/BTCUSDT",
        params={"periods": "15m,1h,15m"},
    )
    assert response.status_code == 422
