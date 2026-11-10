import pytest
from datetime import datetime, timezone

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


class MultiQuoteProvider:
    async def exchange_info(self):
        return {"symbols": [
            {"symbol": "AAAUSDT", "baseAsset": "AAA", "quoteAsset": "USDT",
             "status": "TRADING", "isSpotTradingAllowed": True, "orderTypes": ["LIMIT"]},
            {"symbol": "AAAUSDC", "baseAsset": "AAA", "quoteAsset": "USDC",
             "status": "TRADING", "isSpotTradingAllowed": True, "orderTypes": ["LIMIT"]},
            {"symbol": "BBBFDUSD", "baseAsset": "BBB", "quoteAsset": "FDUSD",
             "status": "TRADING", "isSpotTradingAllowed": True},
            {"symbol": "OLDUSDT", "baseAsset": "OLD", "quoteAsset": "USDT",
             "status": "BREAK", "isSpotTradingAllowed": True},
        ]}

    async def all_24h_tickers(self):
        return [
            {"symbol": "BTCUSDT", "lastPrice": "60000", "priceChangePercent": "0.5", "quoteVolume": "999"},
            {"symbol": "AAAUSDT", "lastPrice": "2", "priceChangePercent": "1", "quoteVolume": "100", "highPrice": "2.2", "lowPrice": "1.8"},
            {"symbol": "AAAUSDC", "lastPrice": "2", "priceChangePercent": "2", "quoteVolume": "300", "highPrice": "2.1", "lowPrice": "1.9"},
            {"symbol": "BBBFDUSD", "lastPrice": "3", "priceChangePercent": "3", "quoteVolume": "200", "highPrice": "3.2", "lowPrice": "2.8"},
        ]

    async def all_book_tickers(self):
        return [
            {"symbol": "AAAUSDT", "bidPrice": "1.99", "askPrice": "2.01"},
            {"symbol": "AAAUSDC", "bidPrice": "1.99", "askPrice": "2.01"},
            {"symbol": "BBBFDUSD", "bidPrice": "2.99", "askPrice": "3.01"},
        ]


async def test_scan_defaults_to_all_quote_assets_and_consolidates_base_assets():
    result = await scan_spot_markets(MultiQuoteProvider())
    assert result["status"] == "COMPLETED"
    assert result["phase_status"] == "INCOMPLETE"
    assert "order_book_depth" in result["stage1_missing_metrics"]
    assert result["results"][0]["spread_bps"] is not None
    assert result["quote_asset_filter"] is None
    assert result["total_available_pairs"] == 4
    assert result["eligible_symbols"] == 3
    assert result["scanned_symbols"] == 3
    assert result["unique_coin_count"] == 2
    primary = {row["base_asset"]: row["primary_symbol"] for row in result["unique_coins"]}
    assert primary == {"AAA": None, "BBB": "BBBFDUSD"}
    aaa = next(row for row in result["unique_coins"] if row["base_asset"] == "AAA")
    assert aaa["primary_selection_status"] == "NOT_ESTABLISHED_DIFFERENT_QUOTE_ASSETS_NOT_COMPARABLE"
    assert result["excluded_pair_counts"]["BREAK"] == 1


async def test_spot_scanner_excludes_stable_pairs_fiat_and_leveraged_tokens_and_flags_new_listing():
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

    class EligibilityProvider:
        async def exchange_info(self):
            return {"symbols": [
                {"symbol": "AAAUSDT", "baseAsset": "AAA", "quoteAsset": "USDT", "status": "TRADING", "onboardDate": now_ms},
                {"symbol": "USDCUSDT", "baseAsset": "USDC", "quoteAsset": "USDT", "status": "TRADING"},
                {"symbol": "BTCEUR", "baseAsset": "BTC", "quoteAsset": "EUR", "status": "TRADING"},
                {"symbol": "BTCUPUSDT", "baseAsset": "BTCUP", "quoteAsset": "USDT", "status": "TRADING"},
            ]}

        async def all_24h_tickers(self):
            return [{"symbol": "AAAUSDT", "lastPrice": "2", "priceChangePercent": "1",
                     "quoteVolume": "100", "highPrice": "2.1", "lowPrice": "1.9"}]

        async def all_book_tickers(self):
            return [{"symbol": "AAAUSDT", "bidPrice": "1.99", "askPrice": "2.01"}]

    result = await scan_spot_markets(EligibilityProvider())
    assert result["eligible_symbols"] == 1
    assert result["scanned_symbols"] == 1
    assert result["excluded_pair_counts"]["STABLECOIN_VS_STABLECOIN"] == 1
    assert result["excluded_pair_counts"]["FIAT_PAIR"] == 1
    assert result["excluded_pair_counts"]["LEVERAGED_TOKEN"] == 1
    assert result["newly_listed_pairs_30d"][0]["symbol"] == "AAAUSDT"


async def test_spot_scanner_rejects_negative_or_non_finite_volume_filter():
    for value in (-1, float("nan"), float("inf"), True):
        result = await scan_spot_markets(FakeProvider(), min_quote_volume=value)
        assert result["status"] == "FAILED"
        assert result["error_code"] == "INVALID_FILTER"


async def test_spot_scanner_rejects_malformed_exchange_metadata():
    class MalformedProvider:
        async def exchange_info(self):
            return {"symbols": None}

        async def all_24h_tickers(self):
            return []

    result = await scan_spot_markets(MalformedProvider())
    assert result["status"] == "FAILED"
    assert result["error_code"] == "UPSTREAM_INVALID_RESPONSE"
    assert result["results"] == []
