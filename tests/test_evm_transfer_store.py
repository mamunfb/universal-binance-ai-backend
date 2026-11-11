import pytest
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
        "topics": ["0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef", _topic(SENDER), _topic(RECIPIENT)],
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
                "topics": ["0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef", _topic(SENDER), _topic(RECIPIENT)],
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


def test_address_flow_summary_uses_exact_raw_integer_totals(tmp_path):
    store = EVMTransferStore(str(tmp_path / "history.sqlite3"))
    huge = 2**80
    logs = [
        {"topics": ["0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef", _topic(SENDER), _topic(RECIPIENT)],
         "data": hex(huge), "transactionHash": "0x" + "d" * 64,
         "blockNumber": "0x64", "logIndex": "0x0"},
        {"topics": ["0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef", _topic(RECIPIENT), _topic(SENDER)],
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
        "topics": ["0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef", _topic(SENDER), _topic(RECIPIENT)],
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
        {"topics": ["0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef", _topic(RECIPIENT), _topic(SENDER)],
         "data": hex(5 * 10**18), "transactionHash": "0x" + "a" * 64,
         "blockNumber": "0x64", "logIndex": "0x0"},
        {"topics": ["0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef", _topic(SENDER), _topic(RECIPIENT)],
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
        "topics": ["0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef", _topic(SENDER), _topic(second)],
        "data": hex(7 * 10**18), "transactionHash": "0x" + "c" * 64,
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
