import asyncio

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
