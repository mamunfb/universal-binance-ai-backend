import pytest
import asyncio

from app.services.evm_transfer_store import EVMTransferStore, index_erc20_transfer_history

CONTRACT = "0x" + "a" * 40
SENDER = "0x" + "1" * 40
RECIPIENT = "0x" + "2" * 40


def _topic(address):
    return "0x" + address[2:].rjust(64, "0")


def _word(value):
    return "0x" + format(value, "064x")


def test_transfer_store_is_idempotent_and_tracks_coverage(tmp_path):
    store = EVMTransferStore(str(tmp_path / "history.sqlite3"))
    log = {
        "topics": ["0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef", _topic(SENDER), _topic(RECIPIENT)],
        "data": _word(12345), "transactionHash": "0x" + "b" * 64,
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

        async def block_header(self, number):
            return {
                "number": number,
                "hash": "0x" + format(number, "064x"),
                "parent_hash": "0x" + format(max(number - 1, 0), "064x"),
            }

        async def token_transfer_logs(self, contract, start, end, max_block_span):
            assert end - start + 1 <= 2
            return [{
                "topics": ["0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef", _topic(SENDER), _topic(RECIPIENT)],
                "data": _word(100), "transactionHash": "0x" + format(start, "064x"),
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
        assert "malformed" in str(exc)
    else:
        raise AssertionError("Malformed log must not be accepted")
    assert store.coverage(1, CONTRACT) == []


def test_address_flow_summary_uses_exact_raw_integer_totals(tmp_path):
    store = EVMTransferStore(str(tmp_path / "history.sqlite3"))
    huge = 2**80
    logs = [
        {"topics": ["0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef", _topic(SENDER), _topic(RECIPIENT)],
         "data": _word(huge), "transactionHash": "0x" + "d" * 64,
         "blockNumber": "0x64", "logIndex": "0x0"},
        {"topics": ["0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef", _topic(RECIPIENT), _topic(SENDER)],
         "data": _word(100), "transactionHash": "0x" + "e" * 64,
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
        "topics": ["0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef", _topic(SENDER), _topic(RECIPIENT)],
        "data": _word(10**18), "transactionHash": "0x" + "f" * 64,
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
        {"topics": ["0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef", _topic(RECIPIENT), _topic(SENDER)],
         "data": _word(5 * 10**18), "transactionHash": "0x" + "a" * 64,
         "blockNumber": "0x64", "logIndex": "0x0"},
        {"topics": ["0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef", _topic(SENDER), _topic(RECIPIENT)],
         "data": _word(2 * 10**18), "transactionHash": "0x" + "b" * 64,
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
        "topics": ["0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef", _topic(SENDER), _topic(second)],
        "data": _word(7 * 10**18), "transactionHash": "0x" + "c" * 64,
        "blockNumber": "0x64", "logIndex": "0x0",
    }
    store.save_chunk(1, CONTRACT, 100, 100, [log])
    result = store.smart_money_accumulation_trend(1, CONTRACT, 100, 100, 18, registry, 10)
    assert result["windows"] == []
    assert result["window_count_with_activity"] == 0



def test_indexer_does_not_return_provider_exception_details(tmp_path):
    store = EVMTransferStore(str(tmp_path / "history.sqlite3"))

    class BrokenProvider:
        async def chain_id(self):
            return 1

        async def block_number(self):
            return 999

        async def block_header(self, number):
            return {
                "number": number,
                "hash": "0x" + format(number, "064x"),
                "parent_hash": "0x" + format(max(number - 1, 0), "064x"),
            }

        async def token_transfer_logs(self, *args, **kwargs):
            raise RuntimeError("https://rpc.example/rpc?token=secret-value")

    result = asyncio.run(index_erc20_transfer_history(
        BrokenProvider(), store, CONTRACT, 10, 10, 1, 10
    ))
    assert result["status"] == "FAILED"
    assert result["error"] == "UPSTREAM_UNAVAILABLE"
    assert result["error_type"] == "RuntimeError"
    assert "secret-value" not in str(result)


@pytest.mark.parametrize("bad_log", [
    {
        "topics": ["0x" + "0" * 64, _topic(SENDER), _topic(RECIPIENT)],
        "data": "0x01", "transactionHash": "0x" + "a" * 64,
        "blockNumber": "0x64", "logIndex": "0x0",
    },
    {
        "topics": ["0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",
                   _topic(SENDER), _topic(RECIPIENT)],
        "data": "0x" + "00" * 32, "transactionHash": "0x" + "a" * 64,
        "blockNumber": "0x64", "logIndex": "0x0", "address": "0x" + "b" * 40,
    },
    {
        "topics": ["0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",
                   _topic(SENDER), _topic(RECIPIENT)],
        "data": "0x" + "00" * 32, "transactionHash": "0x" + "a" * 64,
        "blockNumber": "0x64", "logIndex": "0x0", "removed": "false",
    },
])
def test_save_chunk_rejects_non_transfer_or_mismatched_logs_without_coverage(tmp_path, bad_log):
    store = EVMTransferStore(str(tmp_path / "history.sqlite3"))
    with pytest.raises(ValueError):
        store.save_chunk(1, CONTRACT, 100, 110, [bad_log])
    assert store.coverage(1, CONTRACT) == []
    assert store.history(1, CONTRACT, 100, 110) == []


@pytest.mark.parametrize("chain_id, contract, start, end", [
    (True, CONTRACT, 100, 110),
    (-1, CONTRACT, 100, 110),
    (1, "0x1234", 100, 110),
    (1, CONTRACT, True, 110),
    (1, CONTRACT, 111, 110),
])
def test_save_chunk_rejects_invalid_index_scope_before_writing(
    tmp_path, chain_id, contract, start, end
):
    store = EVMTransferStore(str(tmp_path / "history.sqlite3"))
    with pytest.raises(ValueError):
        store.save_chunk(chain_id, contract, start, end, [])
    assert store.coverage(1, CONTRACT) == []


@pytest.mark.parametrize("from_block, to_block, chunk_size, max_total_blocks", [
    (True, 10, 2, 10),
    (1, 10, True, 10),
    (1, 10, 2, False),
    (-1, 10, 2, 10),
    (10, 1, 2, 10),
])
def test_indexer_rejects_invalid_integer_controls_before_provider_calls(
    tmp_path, from_block, to_block, chunk_size, max_total_blocks
):
    store = EVMTransferStore(str(tmp_path / "history.sqlite3"))

    class FakeProvider:
        async def chain_id(self):
            raise AssertionError("Provider must not be called for invalid controls")

    with pytest.raises(ValueError):
        asyncio.run(index_erc20_transfer_history(
            FakeProvider(), store, CONTRACT, from_block, to_block,
            chunk_size, max_total_blocks,
        ))


def test_save_chunk_rejects_duplicate_log_identity_atomically(tmp_path):
    store = EVMTransferStore(str(tmp_path / "history.sqlite3"))
    log = {
        "topics": ["0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",
                   _topic(SENDER), _topic(RECIPIENT)],
        "data": _word(123), "transactionHash": "0x" + "a" * 64,
        "blockNumber": "0x64", "logIndex": "0x0",
    }
    conflicting = {**log, "data": _word(456)}
    with pytest.raises(ValueError, match="duplicate"):
        store.save_chunk(1, CONTRACT, 100, 110, [log, conflicting])
    assert store.history(1, CONTRACT, 100, 110) == []
    assert store.coverage(1, CONTRACT) == []


def test_removed_log_is_excluded_and_replayed_canonical_log_is_restored(tmp_path):
    store = EVMTransferStore(str(tmp_path / "history.sqlite3"))
    log = {
        "topics": ["0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",
                   _topic(SENDER), _topic(RECIPIENT)],
        "data": _word(123), "transactionHash": "0x" + "a" * 64,
        "blockNumber": "0x64", "logIndex": "0x0",
    }
    store.save_chunk(1, CONTRACT, 100, 100, [{**log, "removed": True}])
    assert store.history(1, CONTRACT, 100, 100) == []
    store.save_chunk(1, CONTRACT, 100, 100, [log])
    rows = store.history(1, CONTRACT, 100, 100)
    assert len(rows) == 1
    assert rows[0]["amount_raw"] == "123"
    assert rows[0]["removed"] == 0


def test_reorg_checkpoint_invalidates_forked_logs_and_coverage(tmp_path):
    store = EVMTransferStore(str(tmp_path / "history.sqlite3"))

    def log(block, tx):
        return {
            "topics": [
                "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",
                _topic(SENDER), _topic(RECIPIENT),
            ],
            "data": _word(block), "transactionHash": "0x" + tx * 64,
            "blockNumber": hex(block), "logIndex": "0x0",
        }

    original_headers = [
        {"number": 100, "hash": "0x" + "1" * 64, "parent_hash": "0x" + "0" * 64},
        {"number": 110, "hash": "0x" + "2" * 64, "parent_hash": "0x" + "1" * 64},
    ]
    store.save_chunk(1, CONTRACT, 100, 110, [log(100, "a"), log(105, "b"), log(110, "c")],
                     block_headers=original_headers)
    assert len(store.history(1, CONTRACT, 100, 110)) == 3

    replacement_header = {
        "number": 110, "hash": "0x" + "3" * 64, "parent_hash": "0x" + "4" * 64,
    }
    store.save_chunk(1, CONTRACT, 110, 110, [log(110, "d")],
                     block_headers=[replacement_header])

    rows = store.history(1, CONTRACT, 100, 110)
    assert [row["block_number"] for row in rows] == [110, 100]
    coverage = store.range_coverage(1, CONTRACT, 100, 110)
    assert coverage["complete"] is False
    assert coverage["gaps"] == [{"from": 100, "to": 109}]
    with __import__("sqlite3").connect(store.database_path) as connection:
        checkpoint = connection.execute(
            "SELECT block_hash FROM evm_block_headers WHERE chain_id=1 AND block_number=110"
        ).fetchone()
    assert checkpoint[0] == replacement_header["hash"]


def test_changed_chunk_end_checkpoint_invalidates_from_after_unchanged_start(tmp_path):
    store = EVMTransferStore(str(tmp_path / "history.sqlite3"))

    def log(block, tx):
        return {
            "topics": [
                "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",
                _topic(SENDER), _topic(RECIPIENT),
            ],
            "data": _word(block), "transactionHash": "0x" + tx * 64,
            "blockNumber": hex(block), "logIndex": "0x0",
        }

    store.save_chunk(1, CONTRACT, 200, 210,
                     [log(200, "a"), log(205, "b"), log(210, "c")],
                     block_headers=[
                         {"number": 200, "hash": "0x" + "1" * 64, "parent_hash": "0x" + "0" * 64},
                         {"number": 210, "hash": "0x" + "2" * 64, "parent_hash": "0x" + "1" * 64},
                     ])
    store.save_chunk(1, CONTRACT, 210, 210, [log(210, "d")],
                     block_headers=[
                         {"number": 210, "hash": "0x" + "3" * 64, "parent_hash": "0x" + "4" * 64},
                     ])
    assert [row["block_number"] for row in store.history(1, CONTRACT, 200, 210)] == [210, 200]
    assert store.range_coverage(1, CONTRACT, 200, 210)["complete"] is False


def test_reindexing_subrange_checks_neighboring_checkpoints_for_forks(tmp_path):
    store = EVMTransferStore(str(tmp_path / "history.sqlite3"))

    def log(block, tx):
        return {
            "topics": [
                "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",
                _topic(SENDER), _topic(RECIPIENT),
            ],
            "data": _word(block), "transactionHash": "0x" + tx * 64,
            "blockNumber": hex(block), "logIndex": "0x0",
        }

    original_headers = [
        {"number": 100, "hash": "0x" + "1" * 64, "parent_hash": "0x" + "0" * 64},
        {"number": 110, "hash": "0x" + "2" * 64, "parent_hash": "0x" + "1" * 64},
    ]
    store.save_chunk(1, CONTRACT, 100, 110,
                     [log(100, "a"), log(105, "b"), log(110, "c")],
                     block_headers=original_headers)
    assert store.checkpoint_neighbors(1, 105, 105) == [100, 110]

    refreshed_headers = [
        {"number": 100, "hash": "0x" + "1" * 64, "parent_hash": "0x" + "0" * 64},
        {"number": 105, "hash": "0x" + "5" * 64, "parent_hash": "0x" + "4" * 64},
        {"number": 110, "hash": "0x" + "6" * 64, "parent_hash": "0x" + "5" * 64},
    ]
    store.save_chunk(1, CONTRACT, 105, 105, [log(105, "d")],
                     block_headers=refreshed_headers)
    rows = store.history(1, CONTRACT, 100, 110)
    assert [row["block_number"] for row in rows] == [105, 100]
    assert store.range_coverage(1, CONTRACT, 100, 110)["complete"] is False


def test_first_canonical_checkpoint_discards_legacy_unhashed_coverage(tmp_path):
    store = EVMTransferStore(str(tmp_path / "history.sqlite3"))

    def log(block, tx):
        return {
            "topics": [
                "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",
                _topic(SENDER), _topic(RECIPIENT),
            ],
            "data": _word(block), "transactionHash": "0x" + tx * 64,
            "blockNumber": hex(block), "logIndex": "0x0",
        }

    store.save_chunk(1, CONTRACT, 300, 310, [log(300, "a"), log(305, "b")])
    assert len(store.history(1, CONTRACT, 300, 310)) == 2

    store.save_chunk(
        1, CONTRACT, 305, 305, [log(305, "c")],
        block_headers=[{
            "number": 305, "hash": "0x" + "5" * 64,
            "parent_hash": "0x" + "4" * 64,
        }],
    )
    assert [row["block_number"] for row in store.history(1, CONTRACT, 300, 310)] == [305]
    assert store.range_coverage(1, CONTRACT, 300, 310)["complete"] is False


def test_concurrent_same_chain_cross_contract_writes_are_serialized(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    import sqlite3

    database = str(tmp_path / "concurrent.sqlite3")
    stores = [EVMTransferStore(database) for _ in range(8)]
    contracts = ["0x" + format(index + 10, "040x") for index in range(8)]
    header = {
        "number": 500,
        "hash": "0x" + "5" * 64,
        "parent_hash": "0x" + "4" * 64,
    }

    def write(index):
        log = {
            "topics": [
                "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",
                _topic(SENDER), _topic(RECIPIENT),
            ],
            "data": _word(index + 1),
            "transactionHash": "0x" + format(index + 1, "064x"),
            "blockNumber": hex(500),
            "logIndex": "0x0",
        }
        return stores[index].save_chunk(
            1, contracts[index], 500, 500, [log], block_headers=[header]
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        assert list(executor.map(write, range(8))) == [1] * 8

    for index, store in enumerate(stores):
        assert len(store.history(1, contracts[index], 500, 500)) == 1
        assert store.range_coverage(1, contracts[index], 500, 500)["complete"] is True

    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM evm_block_headers WHERE chain_id=1 AND block_number=500"
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM evm_transfer_index_ranges WHERE chain_id=1"
        ).fetchone()[0] == 8


def test_checkpoint_failure_rolls_back_logs_and_coverage_atomically(tmp_path):
    import sqlite3

    database = str(tmp_path / "atomic.sqlite3")
    store = EVMTransferStore(database)
    log = {
        "topics": [
            "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",
            _topic(SENDER), _topic(RECIPIENT),
        ],
        "data": _word(77),
        "transactionHash": "0x" + "7" * 64,
        "blockNumber": hex(700),
        "logIndex": "0x0",
    }
    with sqlite3.connect(database) as connection:
        connection.execute("""
            CREATE TRIGGER reject_test_checkpoint
            BEFORE INSERT ON evm_block_headers
            BEGIN
                SELECT RAISE(ABORT, 'injected checkpoint failure');
            END
        """)

    with pytest.raises(sqlite3.IntegrityError, match="injected checkpoint failure"):
        store.save_chunk(
            1, CONTRACT, 700, 700, [log],
            block_headers=[{
                "number": 700,
                "hash": "0x" + "7" * 64,
                "parent_hash": "0x" + "6" * 64,
            }],
        )

    assert store.history(1, CONTRACT, 700, 700) == []
    assert store.coverage(1, CONTRACT) == []
    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM evm_block_headers WHERE chain_id=1"
        ).fetchone()[0] == 0
