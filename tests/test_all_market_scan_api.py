from fastapi.testclient import TestClient

from app import main
from app.main import app


client = TestClient(app)


def test_combined_market_scan_reports_spot_and_both_futures_families(monkeypatch):
    async def fake_spot(provider, quote_asset=None, min_quote_volume=0.0):
        return {
            "status": "COMPLETED", "phase_status": "INCOMPLETE",
            "total_available_pairs": 20, "eligible_symbols": 12,
            "scanned_symbols": 11, "failed_symbols": 1,
            "results": [{"base_asset": "BTC", "symbol": "BTCUSDT"}],
        }

    async def fake_futures(min_quote_volume=0.0, perpetual_only=False):
        return {
            "status": "COMPLETED", "phase_status": "INCOMPLETE",
            "total_available_contracts": 10, "eligible_contracts": 8,
            "successfully_scanned_contracts": 8, "failed_contracts": 0,
            "unique_underlyings": [{
                "base_asset": "BTC",
                "contracts": [{"market": "USD_M", "symbol": "BTCUSDT"}],
            }, {
                "base_asset": "ETH",
                "contracts": [{"market": "COIN_M", "symbol": "ETHUSD_PERP"}],
            }],
        }

    monkeypatch.setattr(main, "scan_spot_markets", fake_spot)
    monkeypatch.setattr(main, "all_futures_market_scan", fake_futures)

    response = client.get("/api/v1/markets/scan-all")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "COMPLETED"
    assert payload["phase_status"] == "INCOMPLETE"
    assert payload["coverage"]["spot_successfully_scanned_pairs"] == 11
    assert payload["coverage"]["futures_successfully_scanned_contracts"] == 8
    assert payload["coverage"]["unique_underlying_count"] == 2
    btc = next(row for row in payload["unique_underlyings"] if row["base_asset"] == "BTC")
    assert btc["spot_pairs"] == ["BTCUSDT"]
    assert btc["futures_contracts"][0]["market"] == "USD_M"
    assert payload["trading_enabled"] is False
