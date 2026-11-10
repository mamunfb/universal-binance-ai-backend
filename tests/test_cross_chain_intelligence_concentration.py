import asyncio

from app import main


def test_unified_intelligence_adds_verified_wallet_balance_concentration(monkeypatch):
    contract = "0x" + "2" * 40
    address = "0x" + "1" * 40
    monkeypatch.setattr(
        main.settings, "evm_chain_token_contracts",
        '[{"chain_id":1,"asset_id":"sample","contract_address":"' + contract +
        '","rpc_url":"https://rpc.example","chain_name":"Ethereum"}]',
    )
    monkeypatch.setattr(
        main.settings, "evm_wallet_registry",
        '[{"address":"' + address + '","label":"exchange","verification_status":"verified","evidence_url":"https://example.com/evidence","evidence_note":"Operator reviewed evidence"}]',
    )

    async def fake_flows(*args):
        return {"chains": [{"chain_id": 1, "chain_name": "Ethereum",
                            "contract_address": contract, "status": "COMPLETED",
                            "coverage": {"complete": True, "gaps": []}}]}

    async def fake_cohorts(*args):
        return {"chains": [{"chain_id": 1, "contract_address": contract,
                            "status": "COMPLETED", "coverage": {"complete": True, "gaps": []}}]}

    async def fake_snapshot(configs, asset_id, addresses, timeout):
        assert addresses == [address]
        return {"chains": [{
            "status": "COMPLETED", "snapshot_block": 500,
            "snapshot_block_timestamp": 1700000000,
            "snapshot_timestamp_status": "AVAILABLE",
            "token": {"decimals": 2, "total_supply_raw": "10000"},
            "wallets": [{"address": address, "status": "COMPLETED",
                         "balance_raw": "250", "balance_tokens": 2.5}],
        }]}

    class FakeStore:
        def verified_label_flows(self, *args):
            return {"verified_label_flows": {}}

    monkeypatch.setattr(main, "cross_chain_token_flows", fake_flows)
    monkeypatch.setattr(main, "cross_chain_verified_wallet_flows", fake_cohorts)
    monkeypatch.setattr(main, "cross_chain_erc20_snapshot", fake_snapshot)
    monkeypatch.setattr(main, "evm_transfer_store", FakeStore())
    result = asyncio.run(main.cross_chain_token_intelligence("sample", 10, 20, 2, 10, 5))
    concentration = result["chains"][0]["verified_wallet_concentration"]
    assert result["status"] == "COMPLETED"
    assert concentration["snapshot_block"] == 500
    assert concentration["snapshot_block_number"] == 500
    assert concentration["snapshot_block_timestamp"] == 1700000000
    assert concentration["snapshot_timestamp_status"] == "AVAILABLE"
    assert concentration["snapshot_block_time"] is not None
    assert concentration["snapshot_age_seconds"] >= 0
    assert concentration["by_label"]["exchange"]["balance_tokens"] == 2.5
    assert concentration["by_label"]["exchange"]["share_of_total_supply_pct"] == 2.5
    quality = result["chains"][0]["data_quality"]
    assert quality["balance_snapshot_block"] == 500
    assert quality["balance_snapshot_block_number"] == 500
    assert quality["balance_snapshot_block_timestamp"] == 1700000000
    assert quality["balance_snapshot_timestamp_status"] == "AVAILABLE"
    assert quality["balance_snapshot_block_time"] is not None
    assert quality["balance_snapshot_age_seconds"] >= 0
    assert quality["balance_wallets_succeeded"] == 1
    assert quality["chain_result_status"] == "COMPLETED"
    assert quality["component_status"]["indexed_address_flows"] == "COMPLETED"
    assert quality["component_status"]["verified_smart_money"] == "COMPLETED"
    assert quality["component_status"]["verified_entity_flows"] == "COMPLETED"
    assert quality["component_status"]["verified_wallet_concentration"] == "COMPLETED"
    assert quality["incomplete_reasons"] == []
    assert "age is calculated from the chain block timestamp" in quality["freshness_note"]
    assert result["data_quality_summary"]["chains_with_successful_balance_snapshot"] == 1
    envelope = result["data_quality"]
    assert envelope["status"] == "COMPLETED"
    assert envelope["coverage"]["total_chains"] == 1
    assert envelope["freshness"]["balance_snapshots_with_timestamp"] == 1
    assert envelope["freshness"]["chain_snapshots"][0]["snapshot_block_number"] == 500
    assert any("not all token holders" in item for item in envelope["limitations"])
    assert any("INCOMPLETE" in item for item in envelope["interpretation_notes"])


def test_unified_intelligence_refuses_biased_partial_wallet_snapshot(monkeypatch):
    contract = "0x" + "2" * 40
    entries = []
    for index in range(51):
        address = "0x" + format(index + 1, "040x")
        entries.append('{"address":"' + address + '","label":"whale","verification_status":"verified","evidence_url":"https://example.com/evidence","evidence_note":"Reviewed"}')
    monkeypatch.setattr(
        main.settings, "evm_chain_token_contracts",
        '[{"chain_id":1,"asset_id":"sample","contract_address":"' + contract +
        '","rpc_url":"https://rpc.example","chain_name":"Ethereum"}]',
    )
    monkeypatch.setattr(main.settings, "evm_wallet_registry", "[" + ",".join(entries) + "]")

    async def fake_flows(*args):
        return {"chains": [{"chain_id": 1, "chain_name": "Ethereum",
                            "contract_address": contract, "status": "COMPLETED"}]}

    async def fake_cohorts(*args):
        return {"chains": [{"chain_id": 1, "contract_address": contract,
                            "status": "COMPLETED"}]}

    class FakeStore:
        def verified_label_flows(self, *args):
            return {"verified_label_flows": {}}

    monkeypatch.setattr(main, "cross_chain_token_flows", fake_flows)
    monkeypatch.setattr(main, "cross_chain_verified_wallet_flows", fake_cohorts)
    monkeypatch.setattr(main, "evm_transfer_store", FakeStore())
    result = asyncio.run(main.cross_chain_token_intelligence("sample", 10, 20, 18, 10, 5))
    concentration = result["chains"][0]["verified_wallet_concentration"]
    assert concentration["status"] == "INCOMPLETE"
    assert concentration["queried_wallet_count"] == 0
    assert result["status"] == "INCOMPLETE"
