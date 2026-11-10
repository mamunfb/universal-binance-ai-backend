import asyncio

import pytest

from app.services.cross_chain_wallets import parse_chain_rpc_configs, cross_chain_native_wallet_snapshot

ADDRESS = "0x" + "1" * 40


def test_parse_chain_rpc_configs_validates_chain_and_https():
    parsed = parse_chain_rpc_configs('[{"chain_id":1,"rpc_url":"https://rpc.example","chain_name":"Ethereum"}]')
    assert parsed[0]["chain_id"] == 1
    assert parsed[0]["chain_name"] == "Ethereum"
    with pytest.raises(ValueError, match="HTTPS"):
        parse_chain_rpc_configs('[{"chain_id":1,"rpc_url":"http://localhost"}]')
    with pytest.raises(ValueError, match="Duplicate"):
        parse_chain_rpc_configs('[{"chain_id":1,"rpc_url":"https://a"},{"chain_id":1,"rpc_url":"https://b"}]')


def test_cross_chain_snapshot_checks_actual_chain_id_and_keeps_failures(monkeypatch):
    class FakeProvider:
        def __init__(self, url, timeout):
            self.url = url
        async def chain_id(self):
            return 1 if self.url.endswith("good") else 2
        async def native_balance(self, address):
            return 10**18

    monkeypatch.setattr("app.services.cross_chain_wallets.EVMRPCProvider", FakeProvider)
    configs = [
        {"chain_id": 1, "rpc_url": "https://rpc.good", "chain_name": "Ethereum"},
        {"chain_id": 56, "rpc_url": "https://rpc.wrong", "chain_name": "BSC"},
    ]
    result = asyncio.run(cross_chain_native_wallet_snapshot(configs, [ADDRESS]))
    assert result["status"] == "INCOMPLETE"
    assert result["chains"][0]["wallets"][0]["native_balance"] == 1
    assert result["chains"][1]["status"] == "FAILED"
    assert result["chains"][1]["actual_chain_id"] == 2


def test_cross_chain_snapshot_rejects_bad_wallet_address():
    with pytest.raises(ValueError, match="Invalid EVM"):
        asyncio.run(cross_chain_native_wallet_snapshot([], ["not-an-address"]))
