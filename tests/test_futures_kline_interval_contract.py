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


def test_usdm_standard_kline_endpoint_accepts_one_second_interval(monkeypatch):
    provider = FakeFuturesProvider()
    monkeypatch.setattr(main, "get_futures_provider", lambda _market: provider)

    response = client.get(
        "/api/v1/markets/futures/usdm/klines/BTCUSDT",
        params={"interval": "1s", "limit": 100},
    )

    assert response.status_code == 200
    assert response.json()["interval"] == "1s"
    assert provider.calls == [("BTCUSDT", "1s", 100)]


def test_coinm_standard_kline_endpoint_rejects_one_second_interval(monkeypatch):
    def fail_if_called(_market):
        raise AssertionError("provider must not be called for an unsupported interval")

    monkeypatch.setattr(main, "get_futures_provider", fail_if_called)

    response = client.get(
        "/api/v1/markets/futures/coinm/klines/BTCUSD_PERP",
        params={"interval": "1s"},
    )

    assert response.status_code == 422
