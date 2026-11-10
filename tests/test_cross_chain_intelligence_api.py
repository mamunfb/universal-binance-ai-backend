import asyncio

from app import main


def test_unified_intelligence_joins_chain_results(monkeypatch):
    contract = "0x" + "2" * 40
    monkeypatch.setattr(
        main.settings, "evm_chain_token_contracts",
        '[{"chain_id":1,"asset_id":"sample","contract_address":"' + contract +
        '","rpc_url":"https://rpc.example","chain_name":"Ethereum"}]',
    )

    async def fake_flows(*args):
        return {"chains": [{
            "chain_id": 1, "chain_name": "Ethereum", "contract_address": contract,
            "status": "COMPLETED", "coverage": {"complete": True},
            "flow_summary": {"top_net_receivers": [], "top_net_senders": []},
        }]}

    async def fake_cohorts(*args):
        return {"chains": [{
            "chain_id": 1, "chain_name": "Ethereum", "contract_address": contract,
            "status": "COMPLETED", "coverage": {"complete": True},
            "verified_wallet_flow": {}, "accumulation_trend": {},
        }]}

    monkeypatch.setattr(main, "cross_chain_token_flows", fake_flows)
    monkeypatch.setattr(main, "cross_chain_verified_wallet_flows", fake_cohorts)
    result = asyncio.run(main.cross_chain_token_intelligence("sample", 10, 20, 18, 10, 5))
    assert result["status"] == "COMPLETED"
    assert result["chain_count"] == 1
    assert result["chains"][0]["verified_smart_money"]["status"] == "COMPLETED"


def test_unified_intelligence_does_not_hide_missing_cohort(monkeypatch):
    contract = "0x" + "3" * 40
    monkeypatch.setattr(
        main.settings, "evm_chain_token_contracts",
        '[{"chain_id":1,"asset_id":"sample","contract_address":"' + contract +
        '","rpc_url":"https://rpc.example","chain_name":"Ethereum"}]',
    )

    async def fake_flows(*args):
        return {"chains": [{
            "chain_id": 1, "contract_address": contract, "status": "COMPLETED",
        }]}

    async def fake_cohorts(*args):
        return {"chains": []}

    monkeypatch.setattr(main, "cross_chain_token_flows", fake_flows)
    monkeypatch.setattr(main, "cross_chain_verified_wallet_flows", fake_cohorts)
    result = asyncio.run(main.cross_chain_token_intelligence("sample", 10, 20, 18, 10, 5))
    assert result["status"] == "INCOMPLETE"
    assert result["chains"][0]["verified_smart_money"]["status"] == "UNAVAILABLE"
