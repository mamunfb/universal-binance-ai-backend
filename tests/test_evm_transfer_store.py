import pytest
import asyncio

from app.services.evm_transfer_store import EVMTransferStore, index_erc20_transfer_history
from app.providers.evm_rpc import TRANSFER_TOPIC

CONTRACT = "0x" + "a" * 40
SENDER = "0x" + "1" * 40
RECIPIENT = "0x" + "2" * 40


def _topic(address):
    return "0x" + address[2:].rjust(64, "0")


def test_transfer_store_is_idempotent_and_tracks_coverage(tmp_path):
    store = EVMTransferStore(str(tmp_path / "history.sqlite3"))
    log = {
        "topics": [TRANSFER_TOPIC, _topic(SENDER), _topic(RECIPIENT)],
        "data": hex(12345), "transactionHash": "0x" + "b" * 64,
        "blockNumber": "0x64", "logIndex": "0x0",
    }
    assert store.save_chunk(1, CONTRACT, 100, 110, [log]) == 1
    assert store.save_chunk(1, CONTRACT, 100, 110, [log]) == 1
    rows = store.history(1, CONTRACT, 100, 110)
    assert len(rows) == 1
    assert rows[0]["amount_raw"] == "12345"
    assert store.coverage(1, CONTRACT)[0]["transfer_count"] == 1


def test_indexer_chunks_and_persists_all_ranges(tmp_path):
    store = EVMTransferStore(str(tmp_path / "history.sqlite3"))

    class FakeProvider:
        async def chain_id(self):
            return 1

        async def block_number(self):
            return 999

        async def token_transfer_logs(self, contract, start, end, max_block_span):
            assert end - start + 1 <= 2
            return [{
                "topics": [TRANSFER_TOPIC, _topic(SENDER), _topic(RECIPIENT)],
                "data": hex(100), "transactionHash": "0x" + format(start, "064x"),
                "blockNumber": hex(start), "logIndex": "0x0",
            }]

    result = asyncio.run(index_erc20_transfer_history(
        FakeProvider(), store, CONTRACT, 10, 14, 2, 10
    ))
    assert result["status"] == "COMPLETED"
    assert result["completed_chunks"] == 3
    assert result["next_block_to_retry"] is None
    assert len(store.history(1, CONTRACT, 10, 14)) == 3
    assert [(r["from_block"], r["to_block"]) for r in store.coverage(1, CONTRACT)] == [
        (10, 11), (12, 13), (14, 14)
    ]


def test_indexer_rejects_oversized_range_before_rpc(tmp_path):
    store = EVMTransferStore(str(tmp_path / "history.sqlite3"))

    class FakeProvider:
        async def chain_id(self):
            raise AssertionError("Must reject before RPC")

    try:
        asyncio.run(index_erc20_transfer_history(FakeProvider(), store, CONTRACT, 1, 20, 2, 10))
    except ValueError as exc:
        assert "exceeds maximum" in str(exc)
    else:
        raise AssertionError("Expected range guard")


@pytest.mark.parametrize(
    "chain_id,contract,start,end",
    [
        (0, CONTRACT, 1, 2),
        (-1, CONTRACT, 1, 2),
        (True, CONTRACT, 1, 2),
        (1, "not-an-address", 1, 2),
        (1, "0x" + "g" * 40, 1, 2),
        (1, CONTRACT, -1, 2),
        (1, CONTRACT, 2, 1),
        (1, CONTRACT, True, 2),
        (1, CONTRACT, 1, False),
    ],
)
def test_save_chunk_rejects_invalid_scope_before_writing(
    tmp_path, chain_id, contract, start, end
):
    store = EVMTransferStore(str(tmp_path / "history.sqlite3"))
    with pytest.raises(ValueError):
        store.save_chunk(chain_id, contract, start, end, [])
    assert store.coverage(1, CONTRACT) == []


def test_save_chunk_rejects_non_list_logs(tmp_path):
    store = EVMTransferStore(str(tmp_path / "history.sqlite3"))
    with pytest.raises(ValueError, match="logs must be a list"):
        store.save_chunk(1, CONTRACT, 1, 2, None)
    assert store.coverage(1, CONTRACT) == []


def test_non_transfer_event_signature_does_not_create_coverage(tmp_path):
    store = EVMTransferStore(str(tmp_path / "history.sqlite3"))
    log = {
        "topics": ["0x" + "0" * 64, _topic(SENDER), _topic(RECIPIENT)],
        "data": hex(1), "transactionHash": "0x" + "c" * 64,
        "blockNumber": "0x64", "logIndex": "0x0",
    }
    with pytest.raises(ValueError, match="non-Transfer"):
        store.save_chunk(1, CONTRACT, 100, 100, [log])
    assert store.coverage(1, CONTRACT) == []


def test_malformed_log_does_not_create_coverage(tmp_path):
    store = EVMTransferStore(str(tmp_path / "history.sqlite3"))
    malformed = {"topics": [], "transactionHash": "0x" + "c" * 64}
    try:
        store.save_chunk(1, CONTRACT, 200, 205, [malformed])
    except ValueError as exc:
        assert "malformed Transfer log" in str(exc)
    else:
        raise AssertionError("Malformed log must not be accepted")
    assert store.coverage(1, CONTRACT) == []


def test_save_chunk_rolls_back_logs_when_coverage_write_fails(tmp_path):
    store = EVMTransferStore(str(tmp_path / "history.sqlite3"))
    with store._connect() as connection:
        connection.execute("""
            CREATE TRIGGER reject_test_coverage
            BEFORE INSERT ON evm_transfer_index_ranges
            BEGIN
                SELECT RAISE(ABORT, 'forced coverage failure');
            END
        """)
    log = {
        "topics": [TRANSFER_TOPIC, _topic(SENDER), _topic(RECIPIENT)],
        "data": hex(123), "transactionHash": "0x" + "9" * 64,
        "blockNumber": "0x64", "logIndex": "0x0",
    }
    with pytest.raises(Exception, match="forced coverage failure"):
        store.save_chunk(1, CONTRACT, 100, 100, [log])
    with store._connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM evm_transfer_logs").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM evm_transfer_index_ranges").fetchone()[0] == 0


def test_address_flow_summary_uses_exact_raw_integer_totals(tmp_path):
    store = EVMTransferStore(str(tmp_path / "history.sqlite3"))
    huge = 2**80
    logs = [
        {"topics": [TRANSFER_TOPIC, _topic(SENDER), _topic(RECIPIENT)],
         "data": hex(huge), "transactionHash": "0x" + "d" * 64,
         "blockNumber": "0x64", "logIndex": "0x0"},
        {"topics": [TRANSFER_TOPIC, _topic(RECIPIENT), _topic(SENDER)],
         "data": hex(100), "transactionHash": "0x" + "e" * 64,
         "blockNumber": "0x65", "logIndex": "0x0"},
    ]
    store.save_chunk(1, CONTRACT, 100, 101, logs)
    result = store.address_flow_summary(1, CONTRACT, 100, 101, 0, 10)
    receivers = {row["address"]: row for row in result["top_net_receivers"]}
    assert receivers[SENDER]["net_received_raw"] == str(100 - huge)
    assert receivers[RECIPIENT]["net_received_raw"] == str(huge - 100)


def test_range_coverage_detects_gaps_and_merges_overlaps(tmp_path):
    store = EVMTransferStore(str(tmp_path / "history.sqlite3"))
    store.save_chunk(1, CONTRACT, 100, 109, [])
    store.save_chunk(1, CONTRACT, 110, 119, [])
    complete = store.range_coverage(1, CONTRACT, 103, 117)
    assert complete["complete"] is True
    assert complete["gaps"] == []
    incomplete = store.range_coverage(1, CONTRACT, 100, 125)
    assert incomplete["complete"] is False
    assert incomplete["gaps"] == [{"from": 120, "to": 125}]


def test_smart_money_activity_only_includes_verified_registry_addresses(tmp_path):
    from app.services.wallet_attribution import load_wallet_registry

    store = EVMTransferStore(str(tmp_path / "history.sqlite3"))
    registry_json = '[{"address":"' + SENDER + '","label":"smart_money","entity_name":"Reviewed wallet","verification_status":"verified","evidence_url":"https://example.org/proof","evidence_note":"Operator reviewed public disclosure"}]'
    registry = load_wallet_registry(registry_json, 1)
    log = {
        "topics": [TRANSFER_TOPIC, _topic(SENDER), _topic(RECIPIENT)],
        "data": hex(10**18), "transactionHash": "0x" + "f" * 64,
        "blockNumber": "0x64", "logIndex": "0x0",
    }
    store.save_chunk(1, CONTRACT, 100, 100, [log])
    result = store.smart_money_activity(1, CONTRACT, 100, 100, 18, registry)
    assert result["verified_smart_money_wallets_found"] == 1
    assert result["wallets"][0]["net_received_raw"] == str(-(10**18))
    assert result["wallets"][0]["flow_direction"] == "NET_OUTFLOW"
    assert result["cohort_summary"]["net_outflow_wallet_count"] == 1
    assert result["cohort_summary"]["direction"] == "NET_OUTFLOW"


def test_smart_money_accumulation_trend_groups_net_flows_by_block_window(tmp_path):
    from app.services.wallet_attribution import load_wallet_registry

    store = EVMTransferStore(str(tmp_path / "history.sqlite3"))
    registry_json = '[{"address":"' + SENDER + '","label":"smart_money","verification_status":"verified","evidence_url":"https://example.org/proof","evidence_note":"Reviewed public evidence"}]'
    registry = load_wallet_registry(registry_json, 1)
    logs = [
        {"topics": [TRANSFER_TOPIC, _topic(RECIPIENT), _topic(SENDER)],
         "data": hex(5 * 10**18), "transactionHash": "0x" + "a" * 64,
         "blockNumber": "0x64", "logIndex": "0x0"},
        {"topics": [TRANSFER_TOPIC, _topic(SENDER), _topic(RECIPIENT)],
         "data": hex(2 * 10**18), "transactionHash": "0x" + "b" * 64,
         "blockNumber": "0x6e", "logIndex": "0x0"},
    ]
    store.save_chunk(1, CONTRACT, 100, 110, logs)
    result = store.smart_money_accumulation_trend(1, CONTRACT, 100, 110, 18, registry, 10)
    assert result["window_count_with_activity"] == 2
    assert result["windows"][0]["net_flow_tokens"] == 5
    assert result["windows"][0]["direction"] == "NET_INFLOW"
    assert result["windows"][1]["net_flow_tokens"] == -2
    assert result["windows"][1]["direction"] == "NET_OUTFLOW"
    assert result["windows"][1]["cumulative_net_flow_tokens"] == 3


def test_smart_money_accumulation_trend_rejects_invalid_window(tmp_path):
    from app.services.wallet_attribution import load_wallet_registry

    store = EVMTransferStore(str(tmp_path / "history.sqlite3"))
    registry = load_wallet_registry("[]", 1)
    with pytest.raises(ValueError, match="window_blocks"):
        store.smart_money_accumulation_trend(1, CONTRACT, 100, 110, 18, registry, 0)



def test_smart_money_trend_cancels_transfers_between_cohort_wallets(tmp_path):
    from app.services.wallet_attribution import load_wallet_registry

    second = "0x" + "3" * 40
    store = EVMTransferStore(str(tmp_path / "history.sqlite3"))
    registry_json = (
        '[{"address":"' + SENDER + '","label":"smart_money","verification_status":"verified",'
        '"evidence_url":"https://example.org/a","evidence_note":"Reviewed disclosure"},'
        '{"address":"' + second + '","label":"smart_money","verification_status":"verified",'
        '"evidence_url":"https://example.org/b","evidence_note":"Reviewed disclosure"}]'
    )
    registry = load_wallet_registry(registry_json, 1)
    log = {
        "topics": [TRANSFER_TOPIC, _topic(SENDER), _topic(second)],
        "data": hex(7 * 10**18), "transactionHash": "0x" + "c" * 64,
        "blockNumber": "0x64", "logIndex": "0x0",
    }
    store.save_chunk(1, CONTRACT, 100, 100, [log])
    result = store.smart_money_accumulation_trend(1, CONTRACT, 100, 100, 18, registry, 10)
    assert result["windows"] == []
    assert result["window_count_with_activity"] == 0


def test_evm_indexer_runs_storage_writes_and_coverage_off_event_loop():
    import threading

    observed = []

    class FakeProvider:
        async def chain_id(self):
            return 1

        async def block_number(self):
            return 100

        async def token_transfer_logs(self, contract, start, end, max_block_span):
            return []

    class FakeStore:
        def save_chunk(self, *args, **kwargs):
            observed.append(threading.get_ident())
            return 0

        def coverage(self, *args):
            observed.append(threading.get_ident())
            return []

    async def invoke():
        loop_thread = threading.get_ident()
        result = await index_erc20_transfer_history(
            FakeProvider(), FakeStore(), CONTRACT, 10, 10, 1, 10
        )
        return loop_thread, result

    loop_thread, result = asyncio.run(invoke())
    assert result["status"] == "COMPLETED"
    assert len(observed) == 2
    assert all(thread_id != loop_thread for thread_id in observed)


def test_postgres_lease_is_rejected_for_sqlite_transfer_store(tmp_path):
    from datetime import datetime, timedelta, timezone
    from uuid import uuid4
    from app.services.collector_lease import CollectorLease

    store = EVMTransferStore(str(tmp_path / "history.sqlite3"))
    lease = CollectorLease(
        lease_name="evm-transfer:1:" + CONTRACT,
        owner_id=uuid4(),
        fencing_token=1,
        lease_expires_at=datetime.now(timezone.utc) + timedelta(seconds=30),
    )
    with pytest.raises(ValueError, match="require PostgreSQL-backed"):
        store.save_chunk(1, CONTRACT, 100, 100, [], lease=lease)
    assert store.coverage(1, CONTRACT) == []


def test_postgres_indexer_acquires_renews_passes_and_releases_lease(monkeypatch):
    from types import SimpleNamespace
    import app.services.evm_transfer_store as evm_module

    lease = SimpleNamespace(fencing_token=9)
    captured = {"saved": [], "released": []}

    class FakeLeaseManager:
        def __init__(self, database_url, lease_name, ttl_seconds):
            captured["manager"] = (database_url, lease_name, ttl_seconds)

        def acquire(self):
            return lease

        def renew(self, current):
            assert current is lease
            return lease

        def release(self, current):
            captured["released"].append(current)
            return True

    class FakeProvider:
        async def chain_id(self):
            return 1

        async def block_number(self):
            return 100

        async def token_transfer_logs(self, contract, start, end, max_block_span):
            return []

    class FakeStore:
        database_url = "postgresql://example/test"

        def save_chunk(self, *args, lease=None):
            captured["saved"].append((args, lease))
            return 0

        def coverage(self, *args):
            return []

    monkeypatch.setattr(evm_module, "PostgresCollectorLease", FakeLeaseManager)
    result = asyncio.run(index_erc20_transfer_history(
        FakeProvider(), FakeStore(), CONTRACT, 10, 11, 1, 10, 45
    ))

    assert result["status"] == "COMPLETED"
    assert captured["manager"] == (
        "postgresql://example/test", f"evm-transfer-indexer:1:{CONTRACT}", 45
    )
    assert len(captured["saved"]) == 2
    assert all(item[1] is lease for item in captured["saved"])
    assert captured["released"] == [lease]


def test_postgres_indexer_rejects_when_contract_lease_is_held(monkeypatch):
    import app.services.evm_transfer_store as evm_module
    from app.services.collector_lease import CollectorLeaseLostError

    class FakeLeaseManager:
        def __init__(self, *_args, **_kwargs):
            pass

        def acquire(self):
            return None

    class FakeProvider:
        async def chain_id(self):
            return 1

    class FakeStore:
        database_url = "postgresql://example/test"

    monkeypatch.setattr(evm_module, "PostgresCollectorLease", FakeLeaseManager)
    with pytest.raises(CollectorLeaseLostError, match="currently owns"):
        asyncio.run(index_erc20_transfer_history(
            FakeProvider(), FakeStore(), CONTRACT, 10, 10, 1, 10, 30
        ))


@pytest.mark.asyncio
async def test_evm_indexer_waits_for_inflight_chunk_write_before_releasing_lease(monkeypatch):
    import threading
    import app.services.evm_transfer_store as evm_module

    started = threading.Event()
    finish = threading.Event()
    released = []

    class FakeLeaseManager:
        def __init__(self, *_args, **_kwargs):
            pass

        def acquire(self):
            return object()

        def renew(self, lease):
            return lease

        def release(self, lease):
            released.append(lease)
            return True

    class FakeProvider:
        async def chain_id(self):
            return 1

        async def block_number(self):
            return 100

        async def token_transfer_logs(self, contract, start, end, max_block_span):
            return []

    class BlockingStore:
        database_url = "postgresql://example/test"

        def save_chunk(self, *args, lease=None):
            started.set()
            if not finish.wait(timeout=2):
                raise TimeoutError("test write was not released")
            return 0

        def coverage(self, *args):
            return []

    monkeypatch.setattr(evm_module, "PostgresCollectorLease", FakeLeaseManager)
    task = asyncio.create_task(index_erc20_transfer_history(
        FakeProvider(), BlockingStore(), CONTRACT, 10, 10, 1, 10, 45
    ))
    assert await asyncio.to_thread(started.wait, 1)

    task.cancel()
    await asyncio.sleep(0.05)
    task.cancel()
    await asyncio.sleep(0.05)
    assert not task.done()
    assert released == []

    finish.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert len(released) == 1



@pytest.mark.asyncio
async def test_evm_indexer_waits_for_inflight_renewal_after_repeated_cancellation(monkeypatch):
    import threading
    from types import SimpleNamespace
    import app.services.evm_transfer_store as evm_module

    renewal_started = threading.Event()
    finish_renewal = threading.Event()
    initial_lease = SimpleNamespace(fencing_token=1)
    renewed_lease = SimpleNamespace(fencing_token=2)
    released = []
    saved = []

    class FakeLeaseManager:
        def __init__(self, *_args, **_kwargs):
            pass

        def acquire(self):
            return initial_lease

        def renew(self, lease):
            assert lease is initial_lease
            renewal_started.set()
            if not finish_renewal.wait(timeout=2):
                raise TimeoutError("test renewal was not released")
            return renewed_lease

        def release(self, lease):
            released.append(lease)
            return True

    class FakeProvider:
        async def chain_id(self):
            return 1

        async def block_number(self):
            return 100

        async def token_transfer_logs(self, contract, start, end, max_block_span):
            return []

    class FakeStore:
        database_url = "postgresql://example/test"

        def save_chunk(self, *args, lease=None):
            saved.append(lease)
            return 0

        def coverage(self, *args):
            return []

    monkeypatch.setattr(evm_module, "PostgresCollectorLease", FakeLeaseManager)
    task = asyncio.create_task(index_erc20_transfer_history(
        FakeProvider(), FakeStore(), CONTRACT, 10, 10, 1, 10, 45
    ))
    assert await asyncio.to_thread(renewal_started.wait, 1)

    task.cancel()
    await asyncio.sleep(0.05)
    task.cancel()
    await asyncio.sleep(0.05)
    assert not task.done()
    assert released == []
    assert saved == []

    finish_renewal.set()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert saved == []
    assert released == [renewed_lease]
