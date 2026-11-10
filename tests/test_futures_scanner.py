from app.services.futures_scanner import scan_futures_markets


class FakeFuturesProvider:
    market = "USD_M"

    async def exchange_info(self):
        return {"symbols": [
            {
                "symbol": "AAAUSDT",
                "baseAsset": "AAA",
                "quoteAsset": "USDT",
                "marginAsset": "USDT",
                "contractType": "PERPETUAL",
                "status": "TRADING",
            },
            {
                "symbol": "BBBUSD_260626",
                "baseAsset": "BBB",
                "quoteAsset": "USD",
                "marginAsset": "BBB",
                "contractType": "CURRENT_QUARTER",
                "status": "TRADING",
            },
            {
                "symbol": "CCCUSDT",
                "baseAsset": "CCC",
                "quoteAsset": "USDT",
                "marginAsset": "USDT",
                "contractType": "PERPETUAL",
                "status": "PENDING_TRADING",
            },
        ]}

    async def all_24h_tickers(self):
        return [{
            "symbol": "AAAUSDT",
            "lastPrice": "12.5",
            "priceChangePercent": "2.0",
            "quoteVolume": "900000",
        }]


async def test_usdm_scanner_filters_trading_perpetual_quote_symbols():
    result = await scan_futures_markets(
        FakeFuturesProvider(), quote_asset="USDT", perpetual_only=True
    )
    assert result["status"] == "COMPLETED"
    assert result["eligible_symbols"] == 1
    assert result["scanned_symbols"] == 1
    assert result["results"][0]["symbol"] == "AAAUSDT"


async def test_futures_scanner_volume_filter():
    result = await scan_futures_markets(
        FakeFuturesProvider(), quote_asset="USDT", min_quote_volume=1_000_000
    )
    assert result["matched_symbols"] == 0
