import pytest

from app.services.market_scanner import scan_spot_markets


class FakeProvider:
    async def exchange_info(self):
        return {
            "symbols": [
                {
                    "symbol": "AAAUSDT",
                    "baseAsset": "AAA",
                    "quoteAsset": "USDT",
                    "status": "TRADING",
                    "isSpotTradingAllowed": True,
                },
                {
                    "symbol": "BBBUSDT",
                    "baseAsset": "BBB",
                    "quoteAsset": "USDT",
                    "status": "BREAK",
                    "isSpotTradingAllowed": True,
                },
            ]
        }

    async def all_24h_tickers(self):
        return [
            {
                "symbol": "AAAUSDT",
                "lastPrice": "2.5",
                "priceChangePercent": "3.2",
                "quoteVolume": "500000",
            }
        ]


async def test_scan_counts_trading_quote_symbols():
    result = await scan_spot_markets(FakeProvider(), quote_asset="USDT")
    assert result["status"] == "COMPLETED"
    assert result["eligible_symbols"] == 1
    assert result["scanned_symbols"] == 1
    assert result["matched_symbols"] == 1
    assert result["results"][0]["symbol"] == "AAAUSDT"


async def test_scan_applies_minimum_quote_volume():
    result = await scan_spot_markets(
        FakeProvider(), quote_asset="USDT", min_quote_volume=600000
    )
    assert result["matched_symbols"] == 0
