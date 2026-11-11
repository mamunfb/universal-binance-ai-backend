import asyncio

import pytest
from fastapi import HTTPException

from app import main


@pytest.mark.parametrize("payload", [
    {"from_block": 10, "to_block": 20, "chunk_size": 5, "fromBlock": 10},
    {"from_block": 10, "to_block": 20, "chunk_size": 5, "unexpected": "ignored"},
])
def test_evm_index_route_rejects_unknown_request_fields_before_rpc(monkeypatch, payload):
    class NoRPCProvider:
        async def chain_id(self):
            raise AssertionError("Unknown fields must be rejected before RPC")

    monkeypatch.setattr(main, "get_evm_provider", lambda: NoRPCProvider())
    with pytest.raises(HTTPException) as exc:
        asyncio.run(main.index_evm_token_history("0x" + "a" * 40, payload))
    assert exc.value.status_code == 422
    assert "Unsupported index request fields" in str(exc.value.detail)


def test_evm_index_route_rejects_boolean_block_values_before_rpc(monkeypatch):
    class NoRPCProvider:
        async def chain_id(self):
            raise AssertionError("Invalid values must be rejected before RPC")

    monkeypatch.setattr(main, "get_evm_provider", lambda: NoRPCProvider())
    with pytest.raises(HTTPException) as exc:
        asyncio.run(main.index_evm_token_history(
            "0x" + "a" * 40, {"from_block": True, "to_block": 20}
        ))
    assert exc.value.status_code == 422
    assert "from_block must be an integer" in str(exc.value.detail)


def test_evm_index_route_rejects_missing_required_fields(monkeypatch):
    class NoRPCProvider:
        async def chain_id(self):
            raise AssertionError("Missing fields must be rejected before RPC")

    monkeypatch.setattr(main, "get_evm_provider", lambda: NoRPCProvider())
    with pytest.raises(HTTPException) as exc:
        asyncio.run(main.index_evm_token_history("0x" + "a" * 40, {"from_block": 10}))
    assert exc.value.status_code == 422
