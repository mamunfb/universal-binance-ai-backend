import pytest
from fastapi.testclient import TestClient

from app import main


client = TestClient(main.app)


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/markets/futures/usdm/klines/BTCUSDT",
        "/api/v1/markets/futures/coinm/klines/BTCUSD_PERP",
    ],
)
def test_futures_standard_kline_endpoints_reject_one_second_interval(
    monkeypatch, path
):
    def fail_if_called(_market):
        raise AssertionError("provider must not be called for an unsupported interval")

    monkeypatch.setattr(main, "get_futures_provider", fail_if_called)

    response = client.get(path, params={"interval": "1s"})

    assert response.status_code == 422
