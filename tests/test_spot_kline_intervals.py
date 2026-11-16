from fastapi.testclient import TestClient

from app import main


client = TestClient(main.app)


class FakeSpotProvider:
    def __init__(self):
        self.calls = []

    async def klines(self, symbol, interval, limit):
        self.calls.append((symbol, interval, limit))
        return [[1700000000000, "1", "2", "0.5", "1.5", "10"]]


def test_spot_kline_endpoint_accepts_one_second_interval(monkeypatch):
    provider = FakeSpotProvider()
    monkeypatch.setattr(main, "get_spot_provider", lambda: provider)

    response = client.get(
        "/api/v1/markets/spot/klines/BTCUSDT",
        params={"interval": "1s", "limit": 100},
    )

    assert response.status_code == 200
    assert response.json()["interval"] == "1s"
    assert response.json()["count"] == 1
    assert provider.calls == [("BTCUSDT", "1s", 100)]


def test_spot_kline_endpoint_rejects_unsupported_interval(monkeypatch):
    def fail_if_called():
        raise AssertionError("provider must not be called for an unsupported interval")

    monkeypatch.setattr(main, "get_spot_provider", fail_if_called)

    response = client.get(
        "/api/v1/markets/spot/klines/BTCUSDT",
        params={"interval": "3h"},
    )

    assert response.status_code == 422


def test_openapi_documents_one_second_spot_interval():
    document = client.get("/openapi.json").json()
    operation = document["paths"]["/api/v1/markets/spot/klines/{symbol}"]["get"]
    interval = next(
        item for item in operation["parameters"] if item["name"] == "interval"
    )
    assert "1s" in interval["schema"]["enum"]
