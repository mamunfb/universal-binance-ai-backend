import asyncio
import httpx
import pytest

from app.providers.evm_rpc import EVMRPCProvider, TRANSFER_TOPIC
from app.services.onchain_intelligence import analyze_erc20_activity, get_evm_wallet_snapshot

ADDRESS_A = "0x" + "1" * 40
ADDRESS_B = "0x" + "2" * 40
CONTRACT = "0x" + "a" * 40


def _topic(address):
    return "0x" + address[2:].rjust(64, "0")


def test_provider_requires_https():
    with pytest.raises(ValueError):
        EVMRPCProvider("http://localhost:8545")


def test_transfer_log_parser_and_exchange_flow():
    log = {"topics": [TRANSFER_TOPIC, _topic(ADDRESS_A), _topic(ADDRESS_B)],
           "data": hex(250_000 * 10**6), "transactionHash": "0x" + "b" * 64,
           "blockNumber": "0x64", "logIndex": "0x0"}

    class FakeProvider:
        async def token_transfer_logs(self, contract, from_block, to_block, max_block_span):
            return [log]

    result = asyncio.run(analyze_erc20_activity(
        FakeProvider(), CONTRACT, 100, 100, 6,
        exchange_addresses={"Example Exchange": ADDRESS_B}, whale_threshold_tokens=100_000,
    ))
    assert result["transfer_count"] == 1
    assert result["whale_candidate_count"] == 1
    assert result["exchange_flow"]["inflow_tokens"] == 250_000
    assert result["exchange_flow"]["outflow_tokens"] == 0


def test_block_range_guard():
    class FakeProvider:
        async def token_transfer_logs(self, *args, **kwargs):
            raise AssertionError("Must reject range before RPC call")
    with pytest.raises(ValueError):
        asyncio.run(analyze_erc20_activity(
            FakeProvider(), CONTRACT, 1, 3000, 18, max_block_span=100
        ))


async def test_wallet_snapshot_reports_partial_failures():
    class FakeProvider:
        async def chain_id(self):
            return 1
        async def block_number(self):
            return 123
        async def native_balance(self, address):
            if address == ADDRESS_B:
                raise RuntimeError("provider unavailable")
            return 10**18
    result = await get_evm_wallet_snapshot(FakeProvider(), [ADDRESS_A, ADDRESS_B])
    assert result["status"] == "INCOMPLETE"
    assert result["block_number"] == 123
    assert result["wallets"][0]["native_balance"] == 1
    assert result["wallets"][1]["status"] == "FAILED"


async def test_rpc_provider_json_rpc_contract():
    def handler(request):
        import json
        payload = json.loads(request.content)
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": payload["id"], "result": "0x1"})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = EVMRPCProvider("https://rpc.example.test")
        assert await provider._rpc("eth_chainId", [], client=client) == "0x1"
