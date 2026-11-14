import os
from uuid import uuid4

import psycopg
import pytest

from app.providers.evm_rpc import TRANSFER_TOPIC
from app.services.collector_lease import CollectorLeaseLostError, PostgresCollectorLease
from app.services.derivatives_ratio_store import DerivativesRatioStore
from app.services.evm_transfer_store import EVMTransferStore


DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "").strip()
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="TEST_DATABASE_URL is required for PostgreSQL integration verification",
)


def _topic(address: str) -> str:
    return "0x" + address[2:].rjust(64, "0")


def test_postgres_derivatives_ratio_write_is_fenced_by_lease():
    suffix = uuid4().hex[:10].upper()
    symbol = f"TEST{suffix}"
    lease_name = f"test-derivatives-ratio:{suffix}"
    manager = PostgresCollectorLease(DATABASE_URL, lease_name, ttl_seconds=30)
    lease = manager.acquire()
    assert lease is not None
    store = DerivativesRatioStore("unused.sqlite3", DATABASE_URL)
    timestamp = 1_800_000_000_000
    try:
        result = store.save(
            "GLOBAL_LONG_SHORT",
            symbol,
            "1h",
            [{
                "symbol": symbol,
                "timestamp": timestamp,
                "longShortRatio": "1.2",
                "longAccount": "0.55",
                "shortAccount": "0.45",
            }],
            source="PostgreSQL lease integration test",
            lease=lease,
        )
        assert result["storage"] == "POSTGRESQL"
        history = store.history("GLOBAL_LONG_SHORT", symbol, "1h")
        assert history["returned_count"] == 1
        assert history["records"][0]["long_short_ratio"] == 1.2
        manager.release(lease)
        with pytest.raises(CollectorLeaseLostError):
            store.save(
                "GLOBAL_LONG_SHORT", symbol, "1h",
                [{
                    "symbol": symbol, "timestamp": timestamp + 3_600_000,
                    "longShortRatio": "1.3", "longAccount": "0.56", "shortAccount": "0.44",
                }],
                lease=lease,
            )
    finally:
        manager.release(lease)
        with psycopg.connect(DATABASE_URL) as connection:
            connection.execute(
                "DELETE FROM public.derivatives_ratio_history WHERE symbol=%s",
                (symbol,),
            )
            connection.execute(
                "DELETE FROM public.collector_leases WHERE lease_name=%s",
                (lease_name,),
            )


def test_postgres_evm_chunk_and_coverage_are_written_under_same_lease():
    suffix = (uuid4().hex + uuid4().hex[:8])
    contract = "0x" + suffix
    sender = "0x" + "1" * 40
    recipient = "0x" + "2" * 40
    transaction_hash = "0x" + uuid4().hex * 2
    lease_name = f"test-evm-transfer:1:{contract}"
    manager = PostgresCollectorLease(DATABASE_URL, lease_name, ttl_seconds=30)
    lease = manager.acquire()
    assert lease is not None
    store = EVMTransferStore("unused.sqlite3", DATABASE_URL)
    log = {
        "topics": [TRANSFER_TOPIC, _topic(sender), _topic(recipient)],
        "data": hex(12345),
        "transactionHash": transaction_hash,
        "blockNumber": "0x64",
        "logIndex": "0x0",
    }
    try:
        assert store.save_chunk(1, contract, 100, 110, [log], lease=lease) == 1
        rows = store.history(1, contract, 100, 110)
        assert len(rows) == 1
        assert rows[0]["amount_raw"] == "12345"
        coverage = store.coverage(1, contract)
        assert len(coverage) == 1
        assert coverage[0]["from_block"] == 100
        assert coverage[0]["to_block"] == 110
        manager.release(lease)
        with pytest.raises(CollectorLeaseLostError):
            store.save_chunk(1, contract, 111, 111, [], lease=lease)
        assert len(store.coverage(1, contract)) == 1
    finally:
        manager.release(lease)
        with psycopg.connect(DATABASE_URL) as connection:
            connection.execute(
                "DELETE FROM public.evm_transfer_logs WHERE chain_id=1 AND contract_address=%s",
                (contract,),
            )
            connection.execute(
                "DELETE FROM public.evm_transfer_index_ranges WHERE chain_id=1 AND contract_address=%s",
                (contract,),
            )
            connection.execute(
                "DELETE FROM public.collector_leases WHERE lease_name=%s",
                (lease_name,),
            )
