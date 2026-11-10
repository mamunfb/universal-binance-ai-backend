from app.services.evm_transfer_store import EVMTransferStore


def test_verified_label_flows_excludes_unverified_and_cancels_internal_net(tmp_path):
    store = EVMTransferStore(str(tmp_path / "flows.sqlite3"))
    a, b, outsider = "0x" + "1" * 40, "0x" + "2" * 40, "0x" + "3" * 40
    contract = "0x" + "4" * 40
    store.save_chunk(1, contract, 10, 10, [
        {"topics": ["0x" + "0" * 64, "0x" + "0" * 24 + a[2:], "0x" + "0" * 24 + b[2:]],
         "transactionHash": "0x" + "a" * 64, "blockNumber": "0xa", "logIndex": "0x0", "data": "0x64"},
        {"topics": ["0x" + "0" * 64, "0x" + "0" * 24 + outsider[2:], "0x" + "0" * 24 + a[2:]],
         "transactionHash": "0x" + "b" * 64, "blockNumber": "0xa", "logIndex": "0x1", "data": "0x32"},
    ])
    registry = {"wallets": [
        {"address": a, "label": "exchange", "verification_status": "verified"},
        {"address": b, "label": "exchange", "verification_status": "verified"},
        {"address": outsider, "label": "exchange", "verification_status": "unverified"},
    ]}
    result = store.verified_label_flows(1, contract, 10, 10, 0, registry)
    exchange = result["verified_label_flows"]["exchange"]
    assert exchange["verified_wallet_count"] == 2
    assert exchange["sent_raw"] == "100"
    assert exchange["received_raw"] == "150"
    assert exchange["net_received_raw"] == "50"
