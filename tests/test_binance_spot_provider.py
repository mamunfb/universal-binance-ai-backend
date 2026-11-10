import pytest

from app.providers.binance_spot import BinanceSpotProvider


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


async def test_spot_klines_passes_symbol_as_encoded_query_parameter(monkeypatch):
    clients = []

    def client_factory(**kwargs):
        client = FakeAsyncClient(**kwargs)
        clients.append(client)
        return client

    monkeypatch.setattr("app.providers.binance_spot.httpx.AsyncClient", client_factory)
    provider = BinanceSpotProvider("https://spot.example.test")

    result = await provider.klines("BTCUSDT&limit=9999", interval="1h", limit=100)

    assert result == [["candle"]]
    assert clients[0].calls == [
        (
            "/api/v3/klines",
            {"symbol": "BTCUSDT&LIMIT=9999", "interval": "1h", "limit": 100},
        )
    ]


@pytest.mark.parametrize("limit", [0, -1, 1001])
async def test_spot_klines_rejects_out_of_range_limit_without_request(monkeypatch, limit):
    def fail_if_called(**_kwargs):
        raise AssertionError("network client must not be created for invalid limit")

    monkeypatch.setattr("app.providers.binance_spot.httpx.AsyncClient", fail_if_called)
    provider = BinanceSpotProvider("https://spot.example.test")

    with pytest.raises(ValueError, match="limit"):
        await provider.klines("BTCUSDT", limit=limit)


async def test_spot_klines_rejects_empty_symbol_without_request(monkeypatch):
    def fail_if_called(**_kwargs):
        raise AssertionError("network client must not be created for empty symbol")

    monkeypatch.setattr("app.providers.binance_spot.httpx.AsyncClient", fail_if_called)
    provider = BinanceSpotProvider("https://spot.example.test")

    with pytest.raises(ValueError, match="symbol"):
        await provider.klines("   ")
