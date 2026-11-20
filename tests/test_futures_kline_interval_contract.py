import pytest
from fastapi.testclient import TestClient

from app import main


client = TestClient(main.app)


class FakeFuturesProvider:
    def __init__(self):
        self.calls = []

    async def klines(self, symbol, interval, limit):
        self.calls.append((symbol, interval, limit))
        return [[1700000000000, "1", "2", "0.5", "1.5", "10"]]


def test_usdm_standard_symbol_kline_endpoint_rejects_one_second_interval(monkeypatch):
    provider = FakeFuturesProvider()
    monkeypatch.setattr(main, "get_futures_provider", lambda _market: provider)

    response = client.get(
        "/api/v1/markets/futures/usdm/klines/BTCUSDT",
        params={"interval": "1s", "limit": 100},
    )

    assert response.status_code == 422
    assert provider.calls == []


def test_coinm_standard_kline_endpoint_rejects_one_second_interval(monkeypatch):
    def fail_if_called(_market):
        raise AssertionError("provider must not be called for an unsupported interval")

    monkeypatch.setattr(main, "get_futures_provider", fail_if_called)

    response = client.get(
        "/api/v1/markets/futures/coinm/klines/BTCUSD_PERP",
        params={"interval": "1s"},
    )

    assert response.status_code == 422


class FakeContinuousFuturesProvider:
    def __init__(self, metadata=None):
        self.metadata = metadata or {
            "symbols": [{
                "symbol": "BTCUSDT", "pair": "BTCUSDT",
                "contractType": "PERPETUAL", "status": "TRADING",
            }]
        }
        self.calls = []

    async def exchange_info(self):
        return self.metadata

    async def continuous_klines(self, pair, contract_type, interval, limit):
        self.calls.append((pair, contract_type, interval, limit))
        return [[1700000000000, "1", "2", "0.5", "1.5", "10"]]


def test_usdm_one_second_endpoint_resolves_symbol_to_pair_and_contract_type(monkeypatch):
    provider = FakeContinuousFuturesProvider()
    monkeypatch.setattr(main, "get_futures_provider", lambda _market: provider)

    response = client.get(
        "/api/v1/markets/futures/usdm/continuous-klines/BTCUSDT",
        params={"interval": "1s", "limit": 100},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"] == "BTCUSDT"
    assert payload["pair"] == "BTCUSDT"
    assert payload["contract_type"] == "PERPETUAL"
    assert payload["interval"] == "1s"
    assert provider.calls == [("BTCUSDT", "PERPETUAL", "1s", 100)]


def test_usdm_one_second_endpoint_rejects_unknown_symbol_without_candles(monkeypatch):
    provider = FakeContinuousFuturesProvider({"symbols": []})
    monkeypatch.setattr(main, "get_futures_provider", lambda _market: provider)

    response = client.get("/api/v1/markets/futures/usdm/continuous-klines/UNKNOWN")

    assert response.status_code == 404
    assert provider.calls == []


def test_usdm_one_second_endpoint_rejects_non_trading_contract(monkeypatch):
    provider = FakeContinuousFuturesProvider({
        "symbols": [{
            "symbol": "BTCUSDT", "pair": "BTCUSDT",
            "contractType": "PERPETUAL", "status": "PENDING_TRADING",
        }]
    })
    monkeypatch.setattr(main, "get_futures_provider", lambda _market: provider)

    response = client.get("/api/v1/markets/futures/usdm/continuous-klines/BTCUSDT")

    assert response.status_code == 422
    assert provider.calls == []


def test_usdm_one_second_endpoint_rejects_missing_pair_metadata(monkeypatch):
    provider = FakeContinuousFuturesProvider({
        "symbols": [{
            "symbol": "BTCUSDT", "contractType": "PERPETUAL", "status": "TRADING",
        }]
    })
    monkeypatch.setattr(main, "get_futures_provider", lambda _market: provider)

    response = client.get("/api/v1/markets/futures/usdm/continuous-klines/BTCUSDT")

    assert response.status_code == 502
    assert provider.calls == []
