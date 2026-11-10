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


class IncompleteProvider:
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
                    "symbol": "BBBUsDT",
                    "baseAsset": "BBB",
                    "quoteAsset": "USDT",
                    "status": "TRADING",
                    "isSpotTradingAllowed": True,
                },
            ]
        }

    async def all_24h_tickers(self):
        return [
            {
                "symbol": "AAAUSDT",
                "lastPrice": "not-a-number",
                "priceChangePercent": "1.0",
                "quoteVolume": "500000",
            }
        ]


async def test_scan_marks_missing_and_malformed_tickers_incomplete():
    result = await scan_spot_markets(IncompleteProvider(), quote_asset="USDT")
    assert result["status"] == "INCOMPLETE"
    assert result["eligible_symbols"] == 2
    assert result["scanned_symbols"] == 0
    assert result["failed_symbols"] == 2
    assert result["matched_symbols"] == 0


class FailingProvider:
    async def exchange_info(self):
        raise RuntimeError("provider unavailable")

    async def all_24h_tickers(self):
        return []


async def test_scan_reports_upstream_failure_without_fabricating_zero_market_result():
    result = await scan_spot_markets(FailingProvider(), quote_asset="USDT")
    assert result["status"] == "FAILED"
    assert result["error"] == "provider unavailable"
    assert result["eligible_symbols"] == 0
    assert result["results"] == []
