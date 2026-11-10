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


class IncompleteFuturesProvider:
    market = "USD_M"

    async def exchange_info(self):
        return {"symbols": [
            {
                "symbol": "AAAUSDT",
                "baseAsset": "AAA",
                "quoteAsset": "USDT",
                "contractType": "PERPETUAL",
                "status": "TRADING",
            },
            {
                "symbol": "BBBUSDT",
                "baseAsset": "BBB",
                "quoteAsset": "USDT",
                "contractType": "PERPETUAL",
                "status": "TRADING",
            },
        ]}

    async def all_24h_tickers(self):
        return [
            {
                "symbol": "AAAUSDT",
                "lastPrice": "NaN",
                "priceChangePercent": "2.0",
                "quoteVolume": "1000",
            }
        ]


async def test_futures_scanner_marks_missing_and_non_finite_tickers_incomplete():
    result = await scan_futures_markets(IncompleteFuturesProvider())
    assert result["status"] == "INCOMPLETE"
    assert result["eligible_symbols"] == 2
    assert result["scanned_symbols"] == 0
    assert result["failed_symbols"] == 2
    assert result["matched_symbols"] == 0


class FailingFuturesProvider:
    market = "USD_M"

    async def exchange_info(self):
        raise RuntimeError("private host or credential detail")

    async def all_24h_tickers(self):
        return []


async def test_futures_scanner_sanitizes_upstream_failure():
    result = await scan_futures_markets(FailingFuturesProvider())
    assert result["status"] == "FAILED"
    assert result["error_code"] == "UPSTREAM_UNAVAILABLE"
    assert "credential detail" not in result["error"]
    assert result["results"] == []


async def test_futures_scanner_rejects_negative_minimum_volume():
    result = await scan_futures_markets(FakeFuturesProvider(), min_quote_volume=-1)
    assert result["status"] == "FAILED"
    assert result["error_code"] == "INVALID_FILTER"


async def test_futures_scanner_rejects_malformed_upstream_shape():
    class MalformedProvider:
        market = "USD_M"

        async def exchange_info(self):
            return {"symbols": None}

        async def all_24h_tickers(self):
            return []

    result = await scan_futures_markets(MalformedProvider())
    assert result["status"] == "FAILED"
    assert result["error_code"] == "UPSTREAM_INVALID_RESPONSE"
    assert result["results"] == []


async def test_futures_scanner_includes_dated_contracts_by_default():
    class AllContractProvider(FakeFuturesProvider):
        async def all_24h_tickers(self):
            return [
                {"symbol": "AAAUSDT", "lastPrice": "12.5", "priceChangePercent": "2.0", "quoteVolume": "900000"},
                {"symbol": "BBBUSD_260626", "lastPrice": "100", "priceChangePercent": "-1.0", "quoteVolume": "1200000"},
            ]

    result = await scan_futures_markets(AllContractProvider())
    assert result["status"] == "COMPLETED"
    assert result["quote_asset_filter"] is None
    assert result["perpetual_only"] is False
    assert result["total_available_contracts"] == 3
    assert result["eligible_symbols"] == 2
    assert result["scanned_symbols"] == 2
    assert {row["contract_type"] for row in result["results"]} == {"PERPETUAL", "CURRENT_QUARTER"}
    assert result["unique_underlying_count"] == 2


async def test_coinm_scanner_handles_contract_status_and_base_volume_schema():
    class CoinMProvider:
        market = "COIN_M"

        async def exchange_info(self):
            return {"symbols": [{
                "symbol": "BTCUSD_PERP", "pair": "BTCUSD",
                "baseAsset": "BTC", "quoteAsset": "USD", "marginAsset": "BTC",
                "contractType": "PERPETUAL", "contractStatus": "TRADING",
                "deliveryDate": 4133404800000,
                "filters": [{"filterType": "PRICE_FILTER", "tickSize": "0.1"}],
            }]}

        async def all_24h_tickers(self):
            return [{
                "symbol": "BTCUSD_PERP", "lastPrice": "50000",
                "priceChangePercent": "1.5", "volume": "10000",
                "baseVolume": "20.0",
            }]

    result = await scan_futures_markets(CoinMProvider())
    assert result["status"] == "COMPLETED"
    assert result["eligible_symbols"] == 1
    assert result["scanned_symbols"] == 1
    assert result["results"][0]["status"] == "TRADING"
    assert result["results"][0]["quote_volume_24h"] == 1_000_000
    assert result["results"][0]["quote_volume_method"] == "DERIVED_BASE_VOLUME_TIMES_LAST_PRICE"
