"""Opt-in PostgreSQL integration test for EVM transfer history and coverage."""
import os
import uuid

import pytest

from app.services.evm_transfer_store import EVMTransferStore


@pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL is not configured; PostgreSQL integration test skipped",
)
def test_evm_transfer_postgres_round_trip_coverage_and_flows(tmp_path):
    store = EVMTransferStore(str(tmp_path / "unused.sqlite3"), os.environ["TEST_DATABASE_URL"])
    chain_id = 31337
    contract = "0x" + (uuid.uuid4().hex + uuid.uuid4().hex[:8])
    tx_hash = "0x" + uuid.uuid4().hex + uuid.uuid4().hex
    sender = "0x" + "1" * 40
    recipient = "0x" + "2" * 40
    start, end = 987654321, 987654322
    log = {
        "topics": ["0x" + "0" * 64, "0x" + sender[2:].rjust(64, "0"),
                   "0x" + recipient[2:].rjust(64, "0")],
        "data": hex(12345), "transactionHash": tx_hash,
        "blockNumber": hex(start), "logIndex": "0x0",
    }
    try:
        assert store.save_chunk(chain_id, contract, start, end, [log]) == 1
        assert store.save_chunk(chain_id, contract, start, end, [log]) == 1
        rows = store.history(chain_id, contract, start, end)
        assert len(rows) == 1
        assert rows[0]["amount_raw"] == "12345"
        assert store.range_coverage(chain_id, contract, start, end)["complete"] is True
        summary = store.address_flow_summary(chain_id, contract, start, end, 0)
        assert summary["top_net_senders"][0]["net_received_raw"] == "-12345"
    finally:
        with store._connect() as connection:
            connection.execute(
                "DELETE FROM public.evm_transfer_logs WHERE chain_id=? AND contract_address=?",
                (chain_id, contract),
            )
            connection.execute(
                "DELETE FROM public.evm_transfer_index_ranges WHERE chain_id=? AND contract_address=?",
                (chain_id, contract),
            )
