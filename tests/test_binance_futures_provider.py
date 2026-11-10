import pytest

from app.providers.binance_futures import BinanceFuturesProvider


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeAsyncClient:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    async def get(self, path, params=None):
        self.calls.append((path, params))
        return FakeResponse([["candle"]])


@pytest.mark.parametrize(
    ("market", "expected_base", "expected_path"),
    [
        ("USD_M", "https://fapi.binance.com", "/fapi/v1/klines"),
        ("COIN_M", "https://dapi.binance.com", "/dapi/v1/klines"),
    ],
)
async def test_futures_klines_use_market_specific_endpoint_and_query_params(
    monkeypatch, market, expected_base, expected_path
):
    clients = []

    def client_factory(**kwargs):
        client = FakeAsyncClient(**kwargs)
        clients.append(client)
        return client

    monkeypatch.setattr("app.providers.binance_futures.httpx.AsyncClient", client_factory)
    provider = BinanceFuturesProvider(market)

    result = await provider.klines("btcusdt", interval="4h", limit=200)

    assert result == [["candle"]]
    assert clients[0].kwargs["base_url"] == expected_base
    assert clients[0].calls == [
        (expected_path, {"symbol": "BTCUSDT", "interval": "4h", "limit": 200})
    ]


@pytest.mark.parametrize("limit", [0, -1, 1501])
async def test_futures_klines_reject_out_of_range_limit(monkeypatch, limit):
    def fail_if_called(**_kwargs):
        raise AssertionError("network client must not be created for invalid limit")

    monkeypatch.setattr("app.providers.binance_futures.httpx.AsyncClient", fail_if_called)
    provider = BinanceFuturesProvider("USD_M")

    with pytest.raises(ValueError, match="limit"):
        await provider.klines("BTCUSDT", limit=limit)


async def test_futures_klines_reject_empty_symbol(monkeypatch):
    def fail_if_called(**_kwargs):
        raise AssertionError("network client must not be created for empty symbol")

    monkeypatch.setattr("app.providers.binance_futures.httpx.AsyncClient", fail_if_called)
    provider = BinanceFuturesProvider("USD_M")

    with pytest.raises(ValueError, match="symbol"):
        await provider.klines(" ")
