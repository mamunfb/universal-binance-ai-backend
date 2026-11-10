from fastapi.testclient import TestClient

from app import main
from app.main import app

client = TestClient(app)


def _candles():
    rows = []
    for i in range(40):
        rows.append({
            "open_time_ms": i * 60_000, "close_time_ms": i * 60_000 + 59_999,
            "open": 100.0, "high": 102.0, "low": 98.0, "close": 100.0,
        })
    rows[10]["high"] = 105.0
    rows[11].update({"high": 106.0, "close": 104.0})
    return rows


def test_liquidity_sweep_confirmation_api_uses_local_stores(monkeypatch):
    candles = _candles()

    class KlineStore:
        def history(self, market, symbol, interval, start_time_ms, end_time_ms, limit):
            assert market == "USD_M"
            assert symbol == "BTCUSDT"
            return {"candles": candles, "coverage": {"contiguous": None}}

    class TradeStore:
        def recent(self, market, symbol, limit, start_time_ms=None, end_time_ms=None):
            return [{
                "trade_time_ms": candles[11]["open_time_ms"] + 1_000,
                "quantity": 2.0, "aggressor_side": "SELL",
            }]

    class BookStore:
        def recent(self, market, symbol, limit, start_time_ms=None, end_time_ms=None):
            return []

    class OIStore:
        def history(self, market, symbol, period, start_time_ms, end_time_ms, limit):
            return {"records": []}

    class FundingStore:
        def history(self, market, symbol, start_time_ms, end_time_ms, limit):
            return {"events": []}

    monkeypatch.setattr(main, "historical_kline_store", KlineStore())
    monkeypatch.setattr(main, "aggregate_trade_store", TradeStore())
    monkeypatch.setattr(main, "order_book_history_store", BookStore())
    monkeypatch.setattr(main, "open_interest_store", OIStore())
    monkeypatch.setattr(main, "funding_rate_store", FundingStore())

    response = client.get(
        "/api/v1/analysis/liquidity-sweep-confirmation/USD_M/BTCUSDT",
        params={"interval": "5m", "limit": 100},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "COMPLETED"
    assert payload["collector_coverage"]["local_history_only"] is True
    assert any(
        item["level"] == 105.0
        and item["aggressor_flow"]["confirmation"] == "OPPOSING_AGGRESSOR_FLOW"
        for item in payload["sweep_candidates"]
    )


def test_liquidity_sweep_confirmation_api_rejects_unknown_interval():
    response = client.get(
        "/api/v1/analysis/liquidity-sweep-confirmation/SPOT/BTCUSDT",
        params={"interval": "2d"},
    )
    assert response.status_code == 422
