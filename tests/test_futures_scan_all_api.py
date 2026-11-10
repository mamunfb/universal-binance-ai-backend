from fastapi.testclient import TestClient

from app import main
from app.main import app

client = TestClient(app)


def test_all_futures_scan_combines_usdm_coinm_and_consolidates_underlyings(monkeypatch):
    async def fake_scan(provider, quote_asset=None, min_quote_volume=0.0, perpetual_only=False):
        if provider.market == "USD_M":
            return {
                "status": "COMPLETED", "total_available_contracts": 3,
                "eligible_symbols": 2, "scanned_symbols": 2, "failed_symbols": 0,
                "results": [
                    {"base_asset": "BTC", "market": "USD_M", "symbol": "BTCUSDT",
                     "contract_type": "PERPETUAL", "margin_asset": "USDT",
                     "quote_asset": "USDT", "quote_volume_24h": 1000},
                ],
            }
        return {
            "status": "COMPLETED", "total_available_contracts": 2,
            "eligible_symbols": 1, "scanned_symbols": 1, "failed_symbols": 0,
            "results": [
                {"base_asset": "BTC", "market": "COIN_M", "symbol": "BTCUSD_PERP",
                 "contract_type": "PERPETUAL", "margin_asset": "BTC",
                 "quote_asset": "USD", "quote_volume_24h": 900},
                {"base_asset": "ETH", "market": "COIN_M", "symbol": "ETHUSD_PERP",
                 "contract_type": "PERPETUAL", "margin_asset": "ETH",
                 "quote_asset": "USD", "quote_volume_24h": 800},
            ],
        }

    monkeypatch.setattr(main, "scan_futures_markets", fake_scan)
    monkeypatch.setattr(main, "get_futures_provider", lambda market: type("Provider", (), {"market": market})())

    response = client.get("/api/v1/markets/futures/scan-all")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "COMPLETED"
    assert payload["total_available_contracts"] == 5
    assert payload["eligible_contracts"] == 3
    assert payload["successfully_scanned_contracts"] == 3
    assert payload["unique_underlying_count"] == 2
    btc = next(item for item in payload["unique_underlyings"] if item["base_asset"] == "BTC")
    assert {item["market"] for item in btc["contracts"]} == {"USD_M", "COIN_M"}
    assert "does not choose a primary contract" in payload["coverage_warning"]
