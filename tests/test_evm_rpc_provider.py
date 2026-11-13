import asyncio
import json

import httpx
import pytest

from app.providers.evm_rpc import EVMRPCProvider


def test_block_timestamp_uses_requested_block_and_decodes_hex(monkeypatch):
    provider = EVMRPCProvider("https://rpc.example")
    calls = []

    async def fake_rpc(method, params, client=None):
        calls.append((method, params))
        return {"timestamp": "0x6553f100"}

    monkeypatch.setattr(provider, "_rpc", fake_rpc)
    result = asyncio.run(provider.block_timestamp(123))
    assert result == int("6553f100", 16)
    assert calls == [("eth_getBlockByNumber", ["0x7b", False])]


@pytest.mark.parametrize("value", [-1, True, 1.5, "123"])
def test_block_timestamp_rejects_invalid_block_number(value):
    provider = EVMRPCProvider("https://rpc.example")
    with pytest.raises(ValueError, match="non-negative integer"):
        asyncio.run(provider.block_timestamp(value))


def test_block_timestamp_rejects_missing_timestamp(monkeypatch):
    provider = EVMRPCProvider("https://rpc.example")

    async def fake_rpc(method, params, client=None):
        return {"number": "0x7b"}

    monkeypatch.setattr(provider, "_rpc", fake_rpc)
    with pytest.raises(ValueError, match="timestamp"):
        asyncio.run(provider.block_timestamp(123))


@pytest.mark.parametrize("timeout", [0, -1, True, float("inf"), "10"])
def test_provider_rejects_invalid_timeout(timeout):
    with pytest.raises(ValueError, match="positive number"):
        EVMRPCProvider("https://rpc.example", timeout)


@pytest.mark.parametrize("response_body, message", [
    ({"jsonrpc": "1.0", "id": 1, "result": "0x1"}, "protocol version"),
    ({"jsonrpc": "2.0", "id": 99, "result": "0x1"}, "response id"),
    ({"jsonrpc": "2.0", "id": 1}, "no result"),
])
def test_rpc_rejects_invalid_response_envelope(response_body, message):
    def handler(request):
        return httpx.Response(200, json=response_body)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            provider = EVMRPCProvider("https://rpc.example")
            with pytest.raises(ValueError, match=message):
                await provider._rpc("eth_chainId", [], client=client)

    asyncio.run(run())


def test_rpc_accepts_matching_json_rpc_envelope():
    def handler(request):
        payload = json.loads(request.content)
        return httpx.Response(200, json={
            "jsonrpc": "2.0", "id": payload["id"], "result": "0x1"
        })

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            provider = EVMRPCProvider("https://rpc.example")
            assert await provider._rpc("eth_chainId", [], client=client) == "0x1"

    asyncio.run(run())


def test_transfer_logs_rejects_invalid_ranges_before_rpc():
    provider = EVMRPCProvider("https://rpc.example")

    async def fail_if_called(*args, **kwargs):
        raise AssertionError("RPC must not be called for invalid ranges")

    provider._rpc = fail_if_called
    for args in [(True, 1, 10), (1, 2.5, 10), (0, 1, 0), (0, 1, True)]:
        with pytest.raises(ValueError):
            asyncio.run(provider.token_transfer_logs("0x" + "1" * 40, *args))


def test_rpc_retries_transient_server_error_then_succeeds():
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503, json={"error": "temporarily unavailable"})
        payload = json.loads(request.content)
        return httpx.Response(200, json={
            "jsonrpc": "2.0", "id": payload["id"], "result": "0x1"
        })

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            provider = EVMRPCProvider("https://rpc.example", retry_attempts=1)
            assert await provider._rpc("eth_chainId", [], client=client) == "0x1"

    asyncio.run(run())
    assert calls == 2


def test_rpc_does_not_retry_client_error():
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(400, json={"error": "bad request"})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            provider = EVMRPCProvider("https://rpc.example", retry_attempts=3)
            with pytest.raises(httpx.HTTPStatusError):
                await provider._rpc("eth_chainId", [], client=client)

    asyncio.run(run())
    assert calls == 1


@pytest.mark.parametrize("attempts", [-1, 4, True, 1.5])
def test_provider_rejects_invalid_retry_attempts(attempts):
    with pytest.raises(ValueError, match="retry_attempts"):
        EVMRPCProvider("https://rpc.example", retry_attempts=attempts)

def test_rpc_error_payload_does_not_disclose_upstream_url_or_credentials():
    secret_url = "https://rpc-user:rpc-password@rpc.example.test/?token=rpc-secret"

    def handler(request):
        payload = json.loads(request.content)
        return httpx.Response(200, json={
            "jsonrpc": "2.0",
            "id": payload["id"],
            "error": {"code": -32000, "message": f"provider failed at {secret_url}"},
        })

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            provider = EVMRPCProvider("https://rpc.example")
            with pytest.raises(RuntimeError, match="JSON-RPC eth_chainId failed") as caught:
                await provider._rpc("eth_chainId", [], client=client)
            for secret in ("rpc-user", "rpc-password", "rpc-secret", secret_url):
                assert secret not in str(caught.value)

    asyncio.run(run())
\n