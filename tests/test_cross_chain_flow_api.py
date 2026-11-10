import asyncio

from app import main


def test_cross_chain_token_flows_reports_per_chain_coverage(monkeypatch):
    contract = "0x" + "2" * 40
    monkeypatch.setattr(main.settings, "evm_chain_token_contracts",
        '[{"chain_id":1,"asset_id":"sample","contract_address":"' + contract +
        '","rpc_url":"https://rpc.example","chain_name":"Ethereum"}]')

    class FakeProvider:
        def __init__(self, url, timeout):
            pass
        async def chain_id(self):
            return 1

    class FakeStore:
        def range_coverage(self, chain_id, address, start, end):
            return {"complete": False, "requested_range": {"from": start, "to": end},
                    "gaps": [{"from": start, "to": end}]}
        def address_flow_summary(self, chain_id, address, start, end, decimals, limit):
            return {"transfer_counted_address_count": 0, "top_net_receivers": [],
                    "top_net_senders": []}

    monkeypatch.setattr(main, "EVMRPCProvider", FakeProvider)
    monkeypatch.setattr(main, "evm_transfer_store", FakeStore())
    result = asyncio.run(main.cross_chain_token_flows("sample", 100, 200, 18, 10))
    assert result["status"] == "INCOMPLETE"
    assert result["chains"][0]["status"] == "INCOMPLETE"
    assert result["chains"][0]["coverage"]["complete"] is False


def test_cross_chain_token_flows_sanitizes_provider_error(monkeypatch):
    contract = "0x" + "2" * 40
    monkeypatch.setattr(main.settings, "evm_chain_token_contracts",
        '[{"chain_id":1,"asset_id":"sample","contract_address":"' + contract +
        '","rpc_url":"https://rpc.example","chain_name":"Ethereum"}]')

    class FakeProvider:
        def __init__(self, url, timeout):
            pass
        async def chain_id(self):
            raise RuntimeError("https://rpc.example/key=secret-token")

    monkeypatch.setattr(main, "EVMRPCProvider", FakeProvider)
    result = asyncio.run(main.cross_chain_token_flows("sample", 100, 200, 18, 10))
    assert result["status"] == "INCOMPLETE"
    assert result["chains"][0]["error"] == "CHAIN_FLOW_UNAVAILABLE"
    assert "secret-token" not in str(result)
