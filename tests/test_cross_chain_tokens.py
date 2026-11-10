import asyncio

import pytest

from app.services.cross_chain_tokens import parse_chain_token_configs, cross_chain_erc20_snapshot

ADDRESS = "0x" + "1" * 40
CONTRACT = "0x" + "2" * 40


def test_parse_chain_token_configs_validates_contracts_and_duplicates():
    raw = '[{"chain_id":1,"asset_id":"usd-coin","contract_address":"' + CONTRACT + '","rpc_url":"https://rpc.example"}]'
    parsed = parse_chain_token_configs(raw)
    assert parsed[0]["asset_id"] == "usd-coin"
    with pytest.raises(ValueError, match="HTTPS"):
        parse_chain_token_configs(raw.replace("https://", "http://"))
    with pytest.raises(ValueError, match="Duplicate"):
        parse_chain_token_configs(raw[:-1] + ',' + raw[1:])


def test_cross_chain_erc20_snapshot_pins_calls_to_observed_block(monkeypatch):
    calls = []

    class FakeProvider:
        def __init__(self, url, timeout):
            self.url = url
        async def chain_id(self):
            return 1
        async def block_number(self):
            return 123
        async def block_timestamp(self, block_number):
            assert block_number == 123
            return 1700000000
        async def eth_call(self, contract, data, block="latest"):
            calls.append((data[:10], block))
            if data == "0x18160ddd":
                return hex(1000)
            if data == "0x313ce567":
                return hex(2)
            if data in ("0x95d89b41", "0x06fdde03"):
                return "0x" + (64).to_bytes(32, "big").hex() + (3).to_bytes(32, "big").hex() + "555344" + "00" * 29
            return hex(250)

    monkeypatch.setattr("app.services.cross_chain_tokens.EVMRPCProvider", FakeProvider)
    config = [{"chain_id": 1, "asset_id": "usd-coin", "contract_address": CONTRACT,
               "rpc_url": "https://rpc.example", "chain_name": "Ethereum"}]
    result = asyncio.run(cross_chain_erc20_snapshot(config, "usd-coin", [ADDRESS]))
    assert result["status"] == "COMPLETED"
    assert result["chains"][0]["snapshot_block"] == 123
    assert result["chains"][0]["snapshot_block_number"] == 123
    assert result["chains"][0]["snapshot_block_timestamp"] == 1700000000
    assert result["chains"][0]["snapshot_timestamp_status"] == "AVAILABLE"
    assert result["chains"][0]["snapshot_block_time"] is not None
    assert result["chains"][0]["snapshot_age_seconds"] >= 0
    assert result["chains"][0]["wallets"][0]["balance_tokens"] == 2.5
    assert calls and all(block == "0x7b" for _, block in calls)


def test_cross_chain_erc20_rejects_unknown_asset_and_bad_address():
    with pytest.raises(ValueError, match="No configured"):
        asyncio.run(cross_chain_erc20_snapshot([], "unknown", [ADDRESS]))
    with pytest.raises(ValueError, match="EVM address"):
        asyncio.run(cross_chain_erc20_snapshot(
            [{"chain_id": 1, "asset_id": "x", "contract_address": CONTRACT,
              "rpc_url": "https://rpc.example", "chain_name": "Ethereum"}],
            "x", ["bad"]))
