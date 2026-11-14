import asyncio
import threading

from app import main


def test_evm_history_and_coverage_queries_run_off_event_loop(monkeypatch):
    observed = []

    class Provider:
        async def chain_id(self):
            return 1

    class Store:
        def history(self, *args):
            observed.append(threading.get_ident())
            return [{"transaction_hash": "0xabc"}]

        def coverage(self, *args):
            observed.append(threading.get_ident())
            return [{"from_block": 1, "to_block": 5}]

    monkeypatch.setattr(main, "get_evm_provider", lambda: Provider())
    monkeypatch.setattr(main, "evm_transfer_store", Store())

    async def invoke():
        loop_thread = threading.get_ident()
        response = await main.get_evm_token_history("0x" + "a" * 40, 1, 5, 10)
        return loop_thread, response

    loop_thread, response = asyncio.run(invoke())
    assert response["returned_count"] == 1
    assert len(observed) == 2
    assert all(thread_id != loop_thread for thread_id in observed)


def test_evm_smart_money_queries_run_off_event_loop(monkeypatch):
    observed = []

    class Provider:
        async def chain_id(self):
            return 1

    class Store:
        def range_coverage(self, *args):
            observed.append(threading.get_ident())
            return {"complete": True, "gaps": []}

        def smart_money_activity(self, *args):
            observed.append(threading.get_ident())
            return {"verified_smart_money_wallets_found": 0, "wallets": []}

        def smart_money_accumulation_trend(self, *args):
            observed.append(threading.get_ident())
            return {"window_count_with_activity": 0, "windows": []}

    monkeypatch.setattr(main, "get_evm_provider", lambda: Provider())
    monkeypatch.setattr(main, "evm_transfer_store", Store())
    monkeypatch.setattr(main.settings, "evm_wallet_registry", "[]")

    async def invoke():
        loop_thread = threading.get_ident()
        response = await main.evm_token_smart_money_activity(
            "0x" + "a" * 40, 1, 5, 18, 10, 2
        )
        return loop_thread, response

    loop_thread, response = asyncio.run(invoke())
    assert response["status"] == "COMPLETED"
    assert len(observed) == 3
    assert all(thread_id != loop_thread for thread_id in observed)


def test_cross_chain_token_flow_queries_run_off_event_loop(monkeypatch):
    observed = []

    class Provider:
        def __init__(self, *_args):
            pass

        async def chain_id(self):
            return 1

    class Store:
        def range_coverage(self, *args):
            observed.append(threading.get_ident())
            return {"complete": True, "gaps": []}

        def address_flow_summary(self, *args):
            observed.append(threading.get_ident())
            return {"transfer_counted_address_count": 0}

    monkeypatch.setattr(
        main, "parse_chain_token_configs",
        lambda _raw: [{
            "asset_id": "sample", "chain_id": 1,
            "contract_address": "0x" + "a" * 40,
            "rpc_url": "https://rpc.example", "chain_name": "Test Chain",
        }],
    )
    monkeypatch.setattr(main, "EVMRPCProvider", Provider)
    monkeypatch.setattr(main, "evm_transfer_store", Store())
    monkeypatch.setattr(main.settings, "evm_chain_token_contracts", "configured")

    async def invoke():
        loop_thread = threading.get_ident()
        response = await main.cross_chain_token_flows("sample", 1, 5, 18, 10)
        return loop_thread, response

    loop_thread, response = asyncio.run(invoke())
    assert response["chain_count"] == 1
    assert response["chains"][0]["status"] == "COMPLETED"
    assert len(observed) == 2
    assert all(thread_id != loop_thread for thread_id in observed)
