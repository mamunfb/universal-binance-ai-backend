from datetime import datetime, timezone
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


async def test_futures_scanner_rejects_boolean_minimum_volume():
    for value in (True, False):
        result = await scan_futures_markets(FakeFuturesProvider(), min_quote_volume=value)
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
    assert result["phase_status"] == "INCOMPLETE"
    assert "order_book_depth" in result["stage1_missing_metrics"]
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
                "deliveryDate": 4133404800000, "contractSize": 100,
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
    assert result["results"][0]["contract_size_usd"] == 100
    assert result["results"][0]["settlement_asset"] == "BTC"


async def test_futures_scanner_flags_newly_onboarded_contract():
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

    class NewlyListedProvider(FakeFuturesProvider):
        async def exchange_info(self):
            return {"symbols": [{
                "symbol": "NEWUSDT", "baseAsset": "NEW", "quoteAsset": "USDT",
                "marginAsset": "USDT", "contractType": "PERPETUAL",
                "status": "TRADING", "onboardDate": now_ms,
            }]}

        async def all_24h_tickers(self):
            return [{"symbol": "NEWUSDT", "lastPrice": "1", "priceChangePercent": "0.5", "quoteVolume": "100000"}]

    result = await scan_futures_markets(NewlyListedProvider())
    assert result["newly_listed_contracts_30d"][0]["symbol"] == "NEWUSDT"
    assert result["results"][0]["onboard_date_ms"] == now_ms


async def test_futures_scanner_adds_mark_price_funding_and_basis_when_available():
    class EnrichedProvider(FakeFuturesProvider):
        async def all_book_tickers(self):
            return [{"symbol": "AAAUSDT", "bidPrice": "12.4", "askPrice": "12.6"}]

        async def premium_index(self):
            return [{
                "symbol": "AAAUSDT", "markPrice": "12.55", "indexPrice": "12.5",
                "lastFundingRate": "0.0001", "nextFundingTime": 1790000000000,
            }]

        async def funding_info(self):
            return [{"symbol": "AAAUSDT", "fundingIntervalHours": 4}]

    result = await scan_futures_markets(EnrichedProvider(), quote_asset="USDT")
    row = result["results"][0]
    assert row["spread_bps"] > 0
    assert row["mark_price"] == 12.55
    assert row["index_price"] == 12.5
    assert row["funding_rate"] == 0.0001
    assert row["funding_interval_hours"] == 4
    assert row["mark_index_basis_bps"] > 0
    assert result["stage1_metrics"]["funding_rate"] == "AVAILABLE"


async def test_futures_underlying_selection_does_not_compare_incomparable_quote_assets():
    class MultiQuoteFuturesProvider(FakeFuturesProvider):
        async def exchange_info(self):
            return {"symbols": [
                {"symbol": "AAAUSDT", "baseAsset": "AAA", "quoteAsset": "USDT", "marginAsset": "USDT", "contractType": "PERPETUAL", "status": "TRADING"},
                {"symbol": "AAAUSD_260626", "baseAsset": "AAA", "quoteAsset": "USD", "marginAsset": "AAA", "contractType": "CURRENT_QUARTER", "status": "TRADING"},
            ]}

        async def all_24h_tickers(self):
            return [
                {"symbol": "AAAUSDT", "lastPrice": "2", "priceChangePercent": "1", "quoteVolume": "100"},
                {"symbol": "AAAUSD_260626", "lastPrice": "2", "priceChangePercent": "1", "quoteVolume": "999999"},
            ]

    result = await scan_futures_markets(MultiQuoteFuturesProvider())
    assert result["unique_underlying_count"] == 1
    underlying = result["unique_underlyings"][0]
    assert underlying["primary_symbol"] is None
    assert underlying["candidate_symbols"] == ["AAAUSD_260626", "AAAUSDT"]
    assert underlying["primary_selection_status"] == "NOT_ESTABLISHED_INCOMPARABLE_QUOTE_OR_MARGIN_ASSETS"
