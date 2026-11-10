import asyncio

from app.services.cross_chain_smart_money import cross_chain_verified_wallet_flows

CONTRACT = "0x" + "2" * 40
ADDRESS = "0x" + "1" * 40


def test_cross_chain_verified_wallet_flows_only_uses_verified_registry(monkeypatch):
    class FakeProvider:
        def __init__(self, url, timeout):
            pass
        async def chain_id(self):
            return 1

    class FakeStore:
        def range_coverage(self, chain_id, contract, start, end):
            return {"complete": True, "gaps": []}
        def smart_money_activity(self, chain_id, contract, start, end, decimals, registry, limit):
            assert [w["address"] for w in registry["wallets"]] == [ADDRESS]
            return {"verified_smart_money_wallets_found": 1, "wallets": [],
                    "cohort_summary": {"direction": "NET_INFLOW"}}

    monkeypatch.setattr("app.services.cross_chain_smart_money.EVMRPCProvider", FakeProvider)
    configs = [{"chain_id": 1, "asset_id": "sample", "contract_address": CONTRACT,
                "rpc_url": "https://rpc.example", "chain_name": "Ethereum"}]
    registry = (
        '[{"address":"' + ADDRESS + '","label":"smart_money","verification_status":"verified",'
        '"evidence_url":"https://source.example/wallet","evidence_note":"Official disclosure"},'
        '{"address":"0x' + '3' * 40 + '","label":"smart_money","verification_status":"pending_review"}]'
    )
    result = asyncio.run(cross_chain_verified_wallet_flows(
        configs, "sample", 10, 20, 18, registry, FakeStore()))
    assert result["status"] == "COMPLETED"
    assert result["chains"][0]["verified_registry_wallet_count"] == 1


def test_cross_chain_smart_money_reports_incomplete_coverage(monkeypatch):
    class FakeProvider:
        def __init__(self, url, timeout):
            pass
        async def chain_id(self):
            return 1

    class FakeStore:
        def range_coverage(self, *args):
            return {"complete": False, "gaps": [{"from": 10, "to": 20}]}
        def smart_money_activity(self, *args):
            return {"verified_smart_money_wallets_found": 0, "wallets": []}

    monkeypatch.setattr("app.services.cross_chain_smart_money.EVMRPCProvider", FakeProvider)
    configs = [{"chain_id": 1, "asset_id": "sample", "contract_address": CONTRACT,
                "rpc_url": "https://rpc.example", "chain_name": "Ethereum"}]
    result = asyncio.run(cross_chain_verified_wallet_flows(
        configs, "sample", 10, 20, 18, "[]", FakeStore()))
    assert result["status"] == "INCOMPLETE"
