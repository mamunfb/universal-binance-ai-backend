from fastapi.testclient import TestClient

from app import main
from app.main import app
from app.services.historical_klines import HistoricalKlineStore

client = TestClient(app)


def _row(ts, open_, high, low, close):
    return [ts, str(open_), str(high), str(low), str(close), "10",
            ts + 59_999, "1000", 20, "4", "400", "0"]


def test_market_regime_api_uses_local_store(monkeypatch, tmp_path):
    store = HistoricalKlineStore(str(tmp_path / "klines.sqlite3"))
    rows = []
    price = 100.0
    for i in range(80):
        next_price = price + (0.15 if i % 2 == 0 else -0.10)
        rows.append(_row(i * 60_000, price, max(price, next_price) + 0.1,
                         min(price, next_price) - 0.1, next_price))
        price = next_price
    store.save_klines("SPOT", "BTCUSDT", "1m", rows)
    monkeypatch.setattr(main, "historical_kline_store", store)

    response = client.get(
        "/api/v1/analysis/market-regime/SPOT/BTCUSDT",
        params={"interval": "1m", "limit": 80},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "COMPLETED"
    assert response.json()["symbol"] == "BTCUSDT"


def test_market_regime_api_validates_limit():
    response = client.get(
        "/api/v1/analysis/market-regime/SPOT/BTCUSDT",
        params={"limit": 20},
    )
    assert response.status_code == 422
