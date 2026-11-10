import asyncio
import httpx
import pytest

from app.providers.evm_rpc import EVMRPCProvider, TRANSFER_TOPIC
from app.services.onchain_intelligence import analyze_erc20_activity, get_evm_wallet_snapshot, get_erc20_token_snapshot, _decode_abi_text, _decode_abi_uint

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
           "data": "0x" + hex(250_000 * 10**6)[2:].rjust(64, "0"), "transactionHash": "0x" + "b" * 64,
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
    activity = {row["address"]: row for row in result["address_activity_in_requested_block_range"]}
    assert activity[ADDRESS_A]["sent_tokens"] == 250_000
    assert activity[ADDRESS_B]["received_tokens"] == 250_000


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
        async def block_timestamp(self, block_number):
            assert block_number == 123
            return 1700000000
        async def native_balance(self, address, block="latest"):
            assert block == "0x7b"
            if address == ADDRESS_B:
                raise RuntimeError("provider unavailable")
            return 10**18
    result = await get_evm_wallet_snapshot(FakeProvider(), [ADDRESS_A, ADDRESS_B])
    assert result["status"] == "INCOMPLETE"
    assert result["block_number"] == 123
    assert result["snapshot_block"] == 123
    assert result["snapshot_block_number"] == 123
    assert result["snapshot_block_timestamp"] == 1700000000
    assert result["snapshot_timestamp_status"] == "AVAILABLE"
    assert result["block_timestamp"] == 1700000000
    assert result["timestamp_status"] == "AVAILABLE"
    assert result["snapshot_age_seconds"] >= 0
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


async def test_erc20_snapshot_reports_tracked_share_not_full_distribution():
    class FakeProvider:
        async def block_number(self):
            return 789
        async def block_timestamp(self, block_number):
            assert block_number == 789
            return 1700000000
        async def eth_call(self, contract, data, block="latest"):
            assert block == "0x315"
            if data == "0x18160ddd": return hex(1_000_000 * 10**6)
            if data == "0x313ce567": return hex(6)
            if data == "0x95d89b41":
                return "0x" + (32).to_bytes(32, "big").hex() + (3).to_bytes(32, "big").hex() + b"ABC".ljust(32, b"\x00").hex()
            if data == "0x06fdde03":
                return "0x" + (32).to_bytes(32, "big").hex() + (7).to_bytes(32, "big").hex() + b"Example".ljust(32, b"\x00").hex()
            if data.endswith(ADDRESS_A[2:].rjust(64, "0")): return hex(250_000 * 10**6)
            raise AssertionError(data)
    result = await get_erc20_token_snapshot(FakeProvider(), CONTRACT, {"wallet-a": ADDRESS_A})
    assert result["snapshot_block"] == 789
    assert result["snapshot_block_number"] == 789
    assert result["snapshot_block_timestamp"] == 1700000000
    assert result["snapshot_timestamp_status"] == "AVAILABLE"
    assert result["snapshot_age_seconds"] >= 0
    assert result["token"]["symbol"] == "ABC"
    assert result["token"]["name"] == "Example"
    assert result["tracked_balances"][0]["balance_tokens"] == 250_000
    assert result["tracked_addresses_combined_share_of_total_supply_pct"] == 25
    assert "NOT complete holder distribution" in result["warning"]


async def test_erc20_snapshot_caps_watchlist_before_rpc():
    class FakeProvider:
        async def eth_call(self, *args):
            raise AssertionError("Should reject before RPC")
    with pytest.raises(ValueError):
        await get_erc20_token_snapshot(FakeProvider(), CONTRACT, {str(i): ADDRESS_A for i in range(51)})


def test_transfer_activity_marks_malformed_logs_incomplete():
    valid_topics = [TRANSFER_TOPIC, _topic(ADDRESS_A), _topic(ADDRESS_B)]
    malformed = [
        {"topics": valid_topics, "data": "0x1234"},
        {"topics": [TRANSFER_TOPIC, "0x" + "z" * 64, _topic(ADDRESS_B)],
         "data": "0x" + "0" * 64},
        None,
    ]

    class FakeProvider:
        async def token_transfer_logs(self, contract, from_block, to_block, max_block_span):
            return malformed

    result = asyncio.run(analyze_erc20_activity(
        FakeProvider(), CONTRACT, 100, 100, 6
    ))
    assert result["status"] == "INCOMPLETE"
    assert result["malformed_log_count"] == 3
    assert result["transfer_count"] == 0


@pytest.mark.parametrize("value", ["0x0", "0x" + "zz" * 32, "0x" + "00" * 31 + "0g"])
def test_abi_text_decoder_returns_none_for_malformed_hex(value):
    assert _decode_abi_text(value) is None


def test_abi_text_decoder_supports_bytes32_and_trims_null_bytes():
    encoded = "0x" + b"USDC".ljust(32, b"\x00").hex()
    assert _decode_abi_text(encoded) == "USDC"


def test_abi_text_decoder_rejects_out_of_bounds_dynamic_string():
    encoded = "0x" + (32).to_bytes(32, "big").hex() + (999).to_bytes(32, "big").hex()
    assert _decode_abi_text(encoded) is None


@pytest.mark.parametrize("value", [
    "0x0", "0x" + "00" * 31, "0x" + "zz" * 32, "0x" + "00" * 33
])
def test_abi_uint_decoder_rejects_non_32_byte_or_invalid_hex(value):
    with pytest.raises(ValueError):
        _decode_abi_uint(value)


def test_abi_uint_decoder_decodes_exact_32_byte_word():
    assert _decode_abi_uint("0x" + (123456).to_bytes(32, "big").hex()) == 123456


async def test_erc20_snapshot_rejects_invalid_contract_and_watchlist_before_rpc():
    class FakeProvider:
        async def block_number(self):
            raise AssertionError("Must validate all addresses before RPC")
    with pytest.raises(ValueError):
        await get_erc20_token_snapshot(FakeProvider(), "not-an-address", {})
    with pytest.raises(ValueError):
        await get_erc20_token_snapshot(FakeProvider(), CONTRACT, {"bad-wallet": "0x1234"})
    with pytest.raises(ValueError):
        await get_erc20_token_snapshot(FakeProvider(), CONTRACT, {" ": ADDRESS_A})
