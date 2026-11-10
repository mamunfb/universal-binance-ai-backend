from app.services.multi_timeframe import analyze_btc_market_condition, analyze_multiple_timeframes


class FakeSpotProvider:
    async def klines(self, symbol, interval, limit):
        base = 100.0 if symbol == "BTCUSDT" else 50.0
        return [
            [i, "0", "0", "0", str(base + i), "1", i + 1]
            for i in range(250)
        ]


async def test_multi_timeframe_returns_all_requested_intervals():
    result = await analyze_multiple_timeframes(FakeSpotProvider(), "btcusdt")
    assert result["status"] == "COMPLETED"
    assert result["symbol"] == "BTCUSDT"
    assert result["completed_timeframes"] == 4
    assert set(result["timeframes"]) == {"15m", "1h", "4h", "1d"}
    assert result["alignment"] == "FULLY_BULLISH_ALIGNMENT"


class ShortKlineProvider:
    async def klines(self, symbol, interval, limit):
        return [[i, "0", "0", "0", "100", "1", i + 1] for i in range(10)]


class MalformedKlineProvider:
    async def klines(self, symbol, interval, limit):
        return [[i, "0", "0", "0", "nan", "1", i + 1] for i in range(250)]


async def test_multi_timeframe_marks_short_history_incomplete():
    result = await analyze_multiple_timeframes(ShortKlineProvider(), "btcusdt")
    assert result["status"] == "INCOMPLETE"
    assert result["completed_timeframes"] == 0
    assert result["alignment"] == "INCOMPLETE"
    assert result["timeframes"]["1h"]["error"] == "INSUFFICIENT_KLINE_DATA"


async def test_multi_timeframe_rejects_non_finite_close_prices():
    result = await analyze_multiple_timeframes(MalformedKlineProvider(), "btcusdt")
    assert result["status"] == "INCOMPLETE"
    assert result["timeframes"]["15m"]["error"] == "INVALID_CLOSE_PRICE"


class EthFailingProvider(FakeSpotProvider):
    async def klines(self, symbol, interval, limit):
        if symbol == "ETHUSDT":
            raise RuntimeError("provider secret should not leak")
        return await super().klines(symbol, interval, limit)

    async def all_24h_tickers(self):
        return [
            {"symbol": "BTCUSDT", "priceChangePercent": "1", "quoteVolume": "100"},
            {"symbol": "ETHUSDT", "priceChangePercent": "2", "quoteVolume": "50"},
        ]


async def test_btc_market_condition_is_incomplete_when_eth_data_fails():
    result = await analyze_btc_market_condition(EthFailingProvider())
    assert result["status"] == "INCOMPLETE"
    assert result["eth_multi_timeframe"]["status"] == "INCOMPLETE"
    assert "provider secret" not in str(result)
