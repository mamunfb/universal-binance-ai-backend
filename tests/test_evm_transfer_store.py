import asyncio

from app.services.evm_transfer_store import EVMTransferStore, index_erc20_transfer_history

CONTRACT = "0x" + "a" * 40
SENDER = "0x" + "1" * 40
RECIPIENT = "0x" + "2" * 40


def _topic(address):
    return "0x" + address[2:].rjust(64, "0")


def test_transfer_store_is_idempotent_and_tracks_coverage(tmp_path):
    store = EVMTransferStore(str(tmp_path / "history.sqlite3"))
    log = {
        "topics": ["0x" + "0" * 64, _topic(SENDER), _topic(RECIPIENT)],
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
                "topics": ["0x" + "0" * 64, _topic(SENDER), _topic(RECIPIENT)],
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
