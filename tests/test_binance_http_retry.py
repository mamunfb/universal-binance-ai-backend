import httpx
import pytest

from app.providers import http_retry


class SequenceClient:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    async def get(self, path, params=None):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def response(status, payload=None, headers=None):
    return httpx.Response(
        status,
        json=payload if payload is not None else {"status": status},
        headers=headers,
        request=httpx.Request("GET", "https://api.binance.test/test"),
    )


async def test_rate_limit_retries_after_retry_after_header(monkeypatch):
    delays = []

    async def fake_sleep(seconds):
        delays.append(seconds)

    monkeypatch.setattr(http_retry.asyncio, "sleep", fake_sleep)
    client = SequenceClient([
        response(429, headers={"Retry-After": "2"}),
        response(200, {"ok": True}),
    ])

    result = await http_retry.get_json_with_retry(client, "/ticker")

    assert result == {"ok": True}
    assert client.calls == 2
    assert delays == [2.0]


async def test_ip_ban_418_is_not_retried(monkeypatch):
    client = SequenceClient([
        response(418, headers={"Retry-After": "120"}),
        response(200, {"must_not": "be requested"}),
    ])

    with pytest.raises(httpx.HTTPStatusError):
        await http_retry.get_json_with_retry(client, "/ticker")

    assert client.calls == 1


async def test_transient_server_error_uses_bounded_exponential_backoff(monkeypatch):
    delays = []

    async def fake_sleep(seconds):
        delays.append(seconds)

    monkeypatch.setattr(http_retry.asyncio, "sleep", fake_sleep)
    client = SequenceClient([response(503), response(200, {"ok": True})])

    result = await http_retry.get_json_with_retry(
        client, "/ticker", base_delay_seconds=0.1, max_backoff_seconds=0.5
    )

    assert result == {"ok": True}
    assert client.calls == 2
    assert delays == [0.1]


async def test_transport_error_is_retried(monkeypatch):
    delays = []

    async def fake_sleep(seconds):
        delays.append(seconds)

    monkeypatch.setattr(http_retry.asyncio, "sleep", fake_sleep)
    request = httpx.Request("GET", "https://api.binance.test/test")
    client = SequenceClient([
        httpx.ConnectError("connection failed", request=request),
        response(200, {"ok": True}),
    ])

    result = await http_retry.get_json_with_retry(client, "/ticker")

    assert result == {"ok": True}
    assert client.calls == 2
    assert delays == [0.25]


async def test_rate_limit_without_retry_after_uses_exponential_backoff(monkeypatch):
    delays = []

    async def fake_sleep(seconds):
        delays.append(seconds)

    monkeypatch.setattr(http_retry.asyncio, "sleep", fake_sleep)
    client = SequenceClient([response(429), response(429), response(429)])

    with pytest.raises(httpx.HTTPStatusError):
        await http_retry.get_json_with_retry(
            client, "/ticker", base_delay_seconds=0.1, max_backoff_seconds=0.15
        )

    assert client.calls == 3
    assert delays == [0.1, 0.15]


def test_retry_after_accepts_http_date():
    from datetime import datetime, timedelta, timezone
    from email.utils import format_datetime

    future = datetime.now(timezone.utc) + timedelta(seconds=30)
    parsed = http_retry._retry_after_seconds(format_datetime(future))
    assert parsed is not None
    assert 0 <= parsed <= 30
