import asyncio

from app import main


def test_single_chain_concentration_uses_pinned_snapshot_freshness(monkeypatch):
    class FakeProvider:
        async def chain_id(self):
            return 1

    address = "0x" + "1" * 40
    monkeypatch.setattr(main, "get_evm_provider", lambda: FakeProvider())
    monkeypatch.setattr(
        main, "load_wallet_registry",
        lambda raw, chain_id: {
            "status": "COMPLETED",
            "wallets": [{
                "address": address,
                "label": "smart_money",
                "entity_name": "Example",
                "verification_status": "verified",
            }],
        },
    )

    async def fake_snapshot(provider, contract, tracked):
        assert tracked == {"smart_money:Example": address}
        return {
            "status": "COMPLETED",
            "snapshot_block": 789,
            "snapshot_block_timestamp": 1700000000,
            "snapshot_timestamp_status": "AVAILABLE",
            "snapshot_block_time": "2023-11-14T22:13:20+00:00",
            "snapshot_age_seconds": 100,
            "token": {"decimals": 2, "total_supply_raw": "10000"},
            "tracked_balances": [{
                "label": "smart_money:Example",
                "address": address,
                "balance_raw": "250",
                "balance_tokens": 2.5,
                "status": "COMPLETED",
            }],
            "failed_balances": [],
            "tracked_addresses_combined_balance_tokens": 2.5,
            "tracked_addresses_combined_share_of_total_supply_pct": 2.5,
        }

    monkeypatch.setattr(main, "get_erc20_token_snapshot", fake_snapshot)
    result = asyncio.run(main.evm_token_concentration("0x" + "2" * 40))

    assert result["snapshot_block_number"] == 789
    assert result["snapshot_block_timestamp"] == 1700000000
    assert result["snapshot_timestamp_status"] == "AVAILABLE"
    assert result["snapshot_block_time"] == "2023-11-14T22:13:20+00:00"
    assert result["snapshot_age_seconds"] == 100
    assert result["tracked_wallet_concentration"]["smart_money"]["balance_tokens"] == 2.5
    assert "same pinned block" in result["warning"]
