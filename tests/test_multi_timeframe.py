from app.services.multi_timeframe import analyze_multiple_timeframes


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
