"""Opt-in PostgreSQL integration test for EVM transfer history and analytics."""
import os
import uuid

import pytest

from app.services.evm_transfer_store import EVMTransferStore
from app.services.collector_lease import PostgresCollectorLease
from app.providers.evm_rpc import TRANSFER_TOPIC


@pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL is not configured; PostgreSQL integration test skipped",
)
def test_evm_transfer_postgres_round_trip_coverage_and_flows(tmp_path):
    database_url = os.environ["TEST_DATABASE_URL"]
    store = EVMTransferStore(str(tmp_path / "unused.sqlite3"), database_url)
    chain_id = 31337
    contract = "0x" + (uuid.uuid4().hex + uuid.uuid4().hex[:8])
    lease_name = f"evm-transfer-indexer:{chain_id}:{contract}"
    lease_manager = PostgresCollectorLease(database_url, lease_name, ttl_seconds=30)
    lease = None
    tx_hash = "0x" + uuid.uuid4().hex + uuid.uuid4().hex
    sender = "0x" + "1" * 40
    recipient = "0x" + "2" * 40
    start, end = 987654321, 987654322
    log = {
        "topics": [TRANSFER_TOPIC, "0x" + sender[2:].rjust(64, "0"),
                   "0x" + recipient[2:].rjust(64, "0")],
        "data": hex(12345), "transactionHash": tx_hash,
        "blockNumber": hex(start), "logIndex": "0x0",
    }
    try:
        with pytest.raises(ValueError, match="require an active collector lease"):
            store.save_chunk(chain_id, contract, start, end, [log])
        lease = lease_manager.acquire()
        assert lease is not None
        assert store.save_chunk(chain_id, contract, start, end, [log], lease=lease) == 1
        assert store.save_chunk(chain_id, contract, start, end, [log], lease=lease) == 1
        rows = store.history(chain_id, contract, start, end)
        assert len(rows) == 1
        assert rows[0]["amount_raw"] == "12345"
        assert store.range_coverage(chain_id, contract, start, end)["complete"] is True
        summary = store.address_flow_summary(chain_id, contract, start, end, 0)
        assert summary["top_net_senders"][0]["net_received_raw"] == "-12345"

        # Exercise dict_row-backed PostgreSQL reads in every analytics method.
        smart_money_registry = {"wallets": [{
            "address": sender,
            "label": "smart_money",
            "verification_status": "verified",
            "entity_name": "Integration-test wallet",
            "evidence_url": "https://example.org/test-evidence",
        }]}
        activity = store.smart_money_activity(
            chain_id, contract, start, end, 0, smart_money_registry
        )
        assert activity["verified_smart_money_wallets_found"] == 1
        assert activity["wallets"][0]["net_received_raw"] == "-12345"

        trend = store.smart_money_accumulation_trend(
            chain_id, contract, start, end, 0, smart_money_registry, window_blocks=1
        )
        assert trend["window_count_with_activity"] == 1
        assert trend["windows"][0]["net_flow_raw"] == "-12345"

        label_registry = {"wallets": [
            {"address": sender, "label": "exchange", "verification_status": "verified"},
            {"address": recipient, "label": "fund", "verification_status": "verified"},
        ]}
        label_flows = store.verified_label_flows(
            chain_id, contract, start, end, 0, label_registry
        )["verified_label_flows"]
        assert label_flows["exchange"]["net_received_raw"] == "-12345"
        assert label_flows["fund"]["net_received_raw"] == "12345"
    finally:
        if lease is not None:
            lease_manager.release(lease)
        with store._connect() as connection:
            connection.execute(
                "DELETE FROM public.evm_transfer_logs WHERE chain_id=? AND contract_address=?",
                (chain_id, contract),
            )
            connection.execute(
                "DELETE FROM public.evm_transfer_index_ranges WHERE chain_id=? AND contract_address=?",
                (chain_id, contract),
            )
            connection.execute(
                "DELETE FROM public.collector_leases WHERE lease_name=?",
                (lease_name,),
            )
