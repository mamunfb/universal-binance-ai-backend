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


async def test_usdm_futures_klines_forward_one_second_interval(monkeypatch):
    clients = []

    def client_factory(**kwargs):
        client = FakeAsyncClient(**kwargs)
        clients.append(client)
        return client

    monkeypatch.setattr("app.providers.binance_futures.httpx.AsyncClient", client_factory)
    provider = BinanceFuturesProvider("USD_M")

    result = await provider.klines("btcusdt", interval="1s", limit=1000)

    assert result == [["candle"]]
    assert clients[0].kwargs["base_url"] == "https://fapi.binance.com"
    assert clients[0].calls == [
        ("/fapi/v1/klines", {"symbol": "BTCUSDT", "interval": "1s", "limit": 1000})
    ]


async def test_usdm_continuous_klines_use_pair_contract_type_and_one_second_interval(monkeypatch):
    clients = []

    def client_factory(**kwargs):
        client = FakeAsyncClient(**kwargs)
        clients.append(client)
        return client

    monkeypatch.setattr("app.providers.binance_futures.httpx.AsyncClient", client_factory)
    provider = BinanceFuturesProvider("USD_M")
    result = await provider.continuous_klines("btcusdt", "perpetual", interval="1s", limit=1000)

    assert result == [["candle"]]
    assert clients[0].kwargs["base_url"] == "https://fapi.binance.com"
    assert clients[0].calls == [(
        "/fapi/v1/continuousKlines",
        {"pair": "BTCUSDT", "contractType": "PERPETUAL", "interval": "1s", "limit": 1000},
    )]


@pytest.mark.parametrize("market", ["COIN_M"])
async def test_continuous_klines_reject_non_usdm_market(monkeypatch, market):
    def fail_if_called(**_kwargs):
        raise AssertionError("network client must not be created for unsupported market")

    monkeypatch.setattr("app.providers.binance_futures.httpx.AsyncClient", fail_if_called)
    with pytest.raises(ValueError, match="only for USD_M"):
        await BinanceFuturesProvider(market).continuous_klines("BTCUSDT", "PERPETUAL")


async def test_futures_klines_pass_time_range_filters(monkeypatch):
    clients = []

    def client_factory(**kwargs):
        client = FakeAsyncClient(**kwargs)
        clients.append(client)
        return client

    monkeypatch.setattr("app.providers.binance_futures.httpx.AsyncClient", client_factory)
    provider = BinanceFuturesProvider("USD_M")
    await provider.klines(
        "BTCUSDT", interval="5m", limit=300,
        start_time_ms=1700000000000, end_time_ms=1700006000000,
    )
    assert clients[0].calls == [(
        "/fapi/v1/klines",
        {
            "symbol": "BTCUSDT", "interval": "5m", "limit": 300,
            "startTime": 1700000000000, "endTime": 1700006000000,
        },
    )]


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


async def test_usdm_price_ticker_uses_futures_endpoint(monkeypatch):
    clients = []
    class PriceClient(FakeAsyncClient):
        async def get(self, path, params=None):
            self.calls.append((path, params))
            return FakeResponse({"symbol": "BTCUSDT", "price": "101"})
    monkeypatch.setattr("app.providers.binance_futures.httpx.AsyncClient",
        lambda **kwargs: clients.append(PriceClient(**kwargs)) or clients[-1])
    result = await BinanceFuturesProvider("USD_M").price_ticker("btcusdt")
    assert result == {"symbol": "BTCUSDT", "price": "101"}
    assert clients[0].calls == [("/fapi/v1/ticker/price", {"symbol": "BTCUSDT"})]


async def test_usdm_funding_rate_passes_time_range_filters(monkeypatch):
    clients = []

    def client_factory(**kwargs):
        client = FakeAsyncClient(**kwargs)
        clients.append(client)
        return client

    monkeypatch.setattr("app.providers.binance_futures.httpx.AsyncClient", client_factory)
    provider = BinanceFuturesProvider("USD_M")
    result = await provider.funding_rate(
        "btcusdt", limit=200, start_time_ms=1700000000000, end_time_ms=1700100000000
    )
    assert result == [["candle"]]
    assert clients[0].calls == [(
        "/fapi/v1/fundingRate",
        {"symbol": "BTCUSDT", "limit": 200,
         "startTime": 1700000000000, "endTime": 1700100000000},
    )]


@pytest.mark.parametrize("limit", [0, -1, 1001])
async def test_funding_rate_rejects_invalid_limit_before_network(monkeypatch, limit):
    def fail_if_called(**_kwargs):
        raise AssertionError("network client must not be created")

    monkeypatch.setattr("app.providers.binance_futures.httpx.AsyncClient", fail_if_called)
    with pytest.raises(ValueError, match="limit"):
        await BinanceFuturesProvider("USD_M").funding_rate("BTCUSDT", limit=limit)

async def test_usdm_open_interest_history_passes_time_range_filters(monkeypatch):
    clients = []

    def client_factory(**kwargs):
        client = FakeAsyncClient(**kwargs)
        clients.append(client)
        return client

    monkeypatch.setattr("app.providers.binance_futures.httpx.AsyncClient", client_factory)
    provider = BinanceFuturesProvider("USD_M")
    result = await provider.open_interest_history(
        "btcusdt", period="15m", limit=200,
        start_time_ms=1700000000000, end_time_ms=1700100000000,
    )
    assert result == [["candle"]]
    assert clients[0].calls == [(
        "/futures/data/openInterestHist",
        {"symbol": "BTCUSDT", "period": "15m", "limit": 200,
         "startTime": 1700000000000, "endTime": 1700100000000},
    )]


@pytest.mark.parametrize("period", ["2w", "1m", ""])
async def test_open_interest_history_rejects_invalid_period(monkeypatch, period):
    def fail_if_called(**_kwargs):
        raise AssertionError("network client must not be created")

    monkeypatch.setattr("app.providers.binance_futures.httpx.AsyncClient", fail_if_called)
    with pytest.raises(ValueError, match="period"):
        await BinanceFuturesProvider("USD_M").open_interest_history("BTCUSDT", period=period)


@pytest.mark.parametrize("limit", [0, -1, 501])
async def test_open_interest_history_rejects_invalid_limit(monkeypatch, limit):
    def fail_if_called(**_kwargs):
        raise AssertionError("network client must not be created")

    monkeypatch.setattr("app.providers.binance_futures.httpx.AsyncClient", fail_if_called)
    with pytest.raises(ValueError, match="limit"):
        await BinanceFuturesProvider("USD_M").open_interest_history("BTCUSDT", limit=limit)


@pytest.mark.parametrize(
    ("market", "expected_base", "prefix"),
    [
        ("USD_M", "https://fapi.binance.com", "/fapi/v1"),
        ("COIN_M", "https://dapi.binance.com", "/dapi/v1"),
    ],
)
async def test_premium_index_and_funding_info_use_market_specific_public_endpoints(
    monkeypatch, market, expected_base, prefix
):
    clients = []

    class MetadataClient(FakeAsyncClient):
        async def get(self, path, params=None):
            self.calls.append((path, params))
            if path.endswith("/premiumIndex"):
                return FakeResponse({
                    "symbol": "BTCUSDT" if market == "USD_M" else "BTCUSD_PERP",
                    "markPrice": "101", "indexPrice": "100",
                    "lastFundingRate": "0.0001", "nextFundingTime": 1700000000000,
                    "time": 1699999999000,
                })
            return FakeResponse([{
                "symbol": "BTCUSDT" if market == "USD_M" else "BTCUSD_PERP",
                "fundingIntervalHours": 4,
            }])

    def client_factory(**kwargs):
        client = MetadataClient(**kwargs)
        clients.append(client)
        return client

    monkeypatch.setattr("app.providers.binance_futures.httpx.AsyncClient", client_factory)
    provider = BinanceFuturesProvider(market)
    premium = await provider.premium_index("btcusdt" if market == "USD_M" else "btcusd_perp")
    funding = await provider.funding_info()

    assert clients[0].kwargs["base_url"] == expected_base
    assert clients[0].calls == [
        (f"{prefix}/premiumIndex", {"symbol": "BTCUSDT" if market == "USD_M" else "BTCUSD_PERP"}),
    ]
    assert premium["markPrice"] == "101"
    assert funding[0]["fundingIntervalHours"] == 4


async def test_coinm_funding_history_uses_coinm_endpoint(monkeypatch):
    clients = []

    class FundingClient(FakeAsyncClient):
        async def get(self, path, params=None):
            self.calls.append((path, params))
            return FakeResponse([{"symbol": "BTCUSD_PERP", "fundingRate": "0.0001"}])

    monkeypatch.setattr(
        "app.providers.binance_futures.httpx.AsyncClient",
        lambda **kwargs: clients.append(FundingClient(**kwargs)) or clients[-1],
    )
    result = await BinanceFuturesProvider("COIN_M").funding_rate("BTCUSD_PERP")
    assert result[0]["fundingRate"] == "0.0001"
    assert clients[0].calls[0][0] == "/dapi/v1/fundingRate"


async def test_coinm_open_interest_and_history_use_coinm_contract_schema(monkeypatch):
    clients = []

    class OIClient(FakeAsyncClient):
        async def get(self, path, params=None):
            self.calls.append((path, params))
            if path == "/dapi/v1/openInterest":
                return FakeResponse({
                    "symbol": "BTCUSD_PERP", "pair": "BTCUSD",
                    "openInterest": "12345", "contractType": "PERPETUAL",
                    "time": 1700000000000,
                })
            return FakeResponse([{
                "pair": "BTCUSD", "contractType": "PERPETUAL",
                "sumOpenInterest": "12345", "timestamp": 1700000000000,
            }])

    def client_factory(**kwargs):
        client = OIClient(**kwargs)
        clients.append(client)
        return client

    monkeypatch.setattr("app.providers.binance_futures.httpx.AsyncClient", client_factory)
    provider = BinanceFuturesProvider("COIN_M")
    current = await provider.open_interest("BTCUSD_PERP")
    history = await provider.open_interest_history(
        "BTCUSD_PERP", period="1h", limit=20, contract_type="PERPETUAL",
    )
    assert current["openInterest"] == "12345"
    assert history[0]["sumOpenInterest"] == "12345"
    assert clients[0].calls == [("/dapi/v1/openInterest", {"symbol": "BTCUSD_PERP"})]
    assert clients[1].calls == [(
        "/futures/data/openInterestHist",
        {"pair": "BTCUSD", "period": "1h", "limit": 20, "contractType": "PERPETUAL"},
    )]
