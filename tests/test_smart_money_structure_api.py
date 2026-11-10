from fastapi.testclient import TestClient

from app import main
from app.main import app
from app.services.historical_klines import HistoricalKlineStore

client = TestClient(app)


def _row(ts, open_, high, low, close):
    return [ts, str(open_), str(high), str(low), str(close), "10",
            ts + 59_999, "1000", 20, "4", "400", "0"]


def test_smart_money_structure_api_uses_local_history(monkeypatch, tmp_path):
    store = HistoricalKlineStore(str(tmp_path / "klines.sqlite3"))
    rows = []
    price = 100.0
    for i in range(100):
        delta = 2.0 if i % 8 < 4 else -1.5
        next_price = price + delta
        rows.append(_row(i * 60_000, price, max(price, next_price) + 0.5,
                         min(price, next_price) - 0.5, next_price))
        price = next_price
    store.save_klines("SPOT", "BTCUSDT", "1m", rows)
    monkeypatch.setattr(main, "historical_kline_store", store)

    response = client.get(
        "/api/v1/analysis/smart-money-structure/SPOT/BTCUSDT",
        params={"interval": "1m", "limit": 100},
    )
    assert response.status_code == 200
    assert response.json()["status"] in {"COMPLETED", "INSUFFICIENT_SWINGS"}


def test_smart_money_structure_api_validates_parameters():
    base = "/api/v1/analysis/smart-money-structure/SPOT/BTCUSDT"
    assert client.get(base, params={"limit": 10}).status_code == 422
    assert client.get(base, params={"swing_left": 0}).status_code == 422
