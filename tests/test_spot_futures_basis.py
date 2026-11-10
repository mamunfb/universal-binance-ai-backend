import pytest

from app.services.spot_futures_basis import analyze_spot_futures_basis


class FakeSpotProvider:
    async def price_ticker(self, symbol):
        return {"symbol": symbol, "price": "100.0"}


class FakeFuturesProvider:
    market = "USD_M"

    async def price_ticker(self, symbol):
        return {"symbol": symbol, "price": "101.5"}

    async def funding_rate(self, symbol, limit):
        return [{"symbol": symbol, "fundingRate": "0.0001", "fundingTime": 1700000000000}]


async def test_spot_futures_basis_calculates_premium_and_funding():
    result = await analyze_spot_futures_basis(FakeSpotProvider(), FakeFuturesProvider(), "btcusdt")
    assert result["status"] == "COMPLETED"
    assert result["symbol"] == "BTCUSDT"
    assert result["price_comparison"]["spot_price"] == 100.0
    assert result["price_comparison"]["futures_price"] == 101.5
    assert result["price_comparison"]["basis"] == 1.5
    assert result["price_comparison"]["basis_percent"] == 1.5
    assert result["price_comparison"]["relationship"] == "FUTURES_PREMIUM"
    assert result["funding"]["funding_rate"] == 0.0001


class DiscountFuturesProvider(FakeFuturesProvider):
    async def price_ticker(self, symbol):
        return {"symbol": symbol, "price": "99.0"}


async def test_spot_futures_basis_identifies_discount():
    result = await analyze_spot_futures_basis(FakeSpotProvider(), DiscountFuturesProvider(), "BTCUSDT")
    assert result["price_comparison"]["relationship"] == "FUTURES_DISCOUNT"
    assert result["price_comparison"]["basis"] == -1.0


class BadFundingProvider(FakeFuturesProvider):
    async def funding_rate(self, symbol, limit):
        raise RuntimeError("private endpoint secret")


async def test_funding_failure_does_not_hide_valid_price_basis():
    result = await analyze_spot_futures_basis(FakeSpotProvider(), BadFundingProvider(), "BTCUSDT")
    assert result["price_comparison"]["status"] == "COMPLETED"
    assert result["funding"]["status"] == "INCOMPLETE"
    assert result["status"] == "INCOMPLETE"
    assert "private endpoint secret" not in str(result)


class WrongSymbolSpotProvider(FakeSpotProvider):
    async def price_ticker(self, symbol):
        return {"symbol": "ETHUSDT", "price": "100.0"}


async def test_basis_rejects_mismatched_symbol_response():
    result = await analyze_spot_futures_basis(WrongSymbolSpotProvider(), FakeFuturesProvider(), "BTCUSDT")
    assert result["status"] == "INCOMPLETE"
    assert result["error"] == "INVALID_OR_MISMATCHED_PRICE_RESPONSE"


class InvalidPriceSpotProvider(FakeSpotProvider):
    async def price_ticker(self, symbol):
        return {"symbol": symbol, "price": "nan"}


async def test_basis_rejects_non_finite_prices():
    result = await analyze_spot_futures_basis(InvalidPriceSpotProvider(), FakeFuturesProvider(), "BTCUSDT")
    assert result["status"] == "INCOMPLETE"


@pytest.mark.parametrize("symbol", ["", "  "])
async def test_basis_rejects_empty_symbol(symbol):
    with pytest.raises(ValueError, match="symbol"):
        await analyze_spot_futures_basis(FakeSpotProvider(), FakeFuturesProvider(), symbol)


async def test_basis_rejects_coinm_provider():
    provider = FakeFuturesProvider()
    provider.market = "COIN_M"
    with pytest.raises(ValueError, match="USD_M"):
        await analyze_spot_futures_basis(FakeSpotProvider(), provider, "BTCUSD_PERP")
