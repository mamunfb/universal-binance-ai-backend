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
        def smart_money_accumulation_trend(self, chain_id, contract, start, end, decimals, registry, window):
            assert window == 250
            return {"window_blocks": window, "windows": [{"direction": "ACCUMULATION"}]}

    monkeypatch.setattr("app.services.cross_chain_smart_money.EVMRPCProvider", FakeProvider)
    configs = [{"chain_id": 1, "asset_id": "sample", "contract_address": CONTRACT,
                "rpc_url": "https://rpc.example", "chain_name": "Ethereum"}]
    registry = (
        '[{"address":"' + ADDRESS + '","label":"smart_money","verification_status":"verified",'
        '"evidence_url":"https://source.example/wallet","evidence_note":"Official disclosure"},'
        '{"address":"0x' + '3' * 40 + '","label":"smart_money","verification_status":"pending_review"}]'
    )
    result = asyncio.run(cross_chain_verified_wallet_flows(
        configs, "sample", 10, 20, 18, registry, FakeStore(), window_blocks=250))
    assert result["status"] == "COMPLETED"
    assert result["chains"][0]["verified_registry_wallet_count"] == 1
    assert result["chains"][0]["accumulation_trend"]["window_blocks"] == 250


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
        def smart_money_accumulation_trend(self, *args):
            return {"window_blocks": 1000, "windows": []}

    monkeypatch.setattr("app.services.cross_chain_smart_money.EVMRPCProvider", FakeProvider)
    configs = [{"chain_id": 1, "asset_id": "sample", "contract_address": CONTRACT,
                "rpc_url": "https://rpc.example", "chain_name": "Ethereum"}]
    result = asyncio.run(cross_chain_verified_wallet_flows(
        configs, "sample", 10, 20, 18, "[]", FakeStore()))
    assert result["status"] == "INCOMPLETE"



def test_cross_chain_smart_money_keeps_chain_failures_isolated(monkeypatch):
    class FakeProvider:
        def __init__(self, url, timeout):
            self.url = url
        async def chain_id(self):
            return 1 if "chain-one" in self.url else 999

    class FakeStore:
        def range_coverage(self, chain_id, contract, start, end):
            return {"complete": True, "gaps": []}
        def smart_money_activity(self, *args):
            return {"verified_smart_money_wallets_found": 0, "wallets": []}
        def smart_money_accumulation_trend(self, *args):
            return {"window_blocks": 1000, "windows": []}

    monkeypatch.setattr("app.services.cross_chain_smart_money.EVMRPCProvider", FakeProvider)
    configs = [
        {"chain_id": 1, "asset_id": "sample", "contract_address": CONTRACT,
         "rpc_url": "https://chain-one.example", "chain_name": "Chain One"},
        {"chain_id": 56, "asset_id": "sample", "contract_address": "0x" + "4" * 40,
         "rpc_url": "https://chain-two.example", "chain_name": "Chain Two"},
    ]
    result = asyncio.run(cross_chain_verified_wallet_flows(
        configs, "sample", 10, 20, 18, "[]", FakeStore()))
    assert result["status"] == "INCOMPLETE"
    assert result["chains"][0]["status"] == "COMPLETED"
    assert result["chains"][1]["status"] == "FAILED"
    assert "chain_id does not match" in result["chains"][1]["error"]


def test_cross_chain_smart_money_rejects_invalid_window_before_rpc():
    class NeverCalledProvider:
        def __init__(self, *args):
            raise AssertionError("RPC must not be created for invalid window")

    import pytest
    from unittest.mock import patch

    configs = [{"chain_id": 1, "asset_id": "sample", "contract_address": CONTRACT,
                "rpc_url": "https://rpc.example", "chain_name": "Ethereum"}]
    with patch("app.services.cross_chain_smart_money.EVMRPCProvider", NeverCalledProvider):
        with pytest.raises(ValueError, match="window_blocks"):
            asyncio.run(cross_chain_verified_wallet_flows(
                configs, "sample", 10, 20, 18, "[]", object(), window_blocks=0))


def test_cross_chain_smart_money_sanitizes_provider_error(monkeypatch):
    class FakeProvider:
        def __init__(self, url, timeout):
            pass
        async def chain_id(self):
            raise RuntimeError("https://rpc.example/key=secret-token")

    class FakeStore:
        pass

    monkeypatch.setattr("app.services.cross_chain_smart_money.EVMRPCProvider", FakeProvider)
    configs = [{"chain_id": 1, "asset_id": "sample", "contract_address": CONTRACT,
                "rpc_url": "https://rpc.example", "chain_name": "Ethereum"}]
    result = asyncio.run(cross_chain_verified_wallet_flows(
        configs, "sample", 10, 20, 18, "[]", FakeStore()))
    assert result["status"] == "INCOMPLETE"
    assert result["chains"][0]["error"] == "SMART_MONEY_ANALYSIS_UNAVAILABLE"
    assert "secret-token" not in str(result)
