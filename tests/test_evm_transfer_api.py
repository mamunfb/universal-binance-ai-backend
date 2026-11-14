from fastapi.testclient import TestClient

from app import main
from app.main import app
from app.services.collector_lease import CollectorLeaseLostError


client = TestClient(app)


def test_evm_indexer_lease_conflict_returns_http_409(monkeypatch):
    async def reject_indexing(*_args, **_kwargs):
        raise CollectorLeaseLostError("lease already held")

    monkeypatch.setattr(main, "get_evm_provider", lambda: object())
    monkeypatch.setattr(main, "index_erc20_transfer_history", reject_indexing)

    response = client.post(
        "/api/v1/onchain/evm/token/0x" + "a" * 40 + "/index",
        json={"from_block": 100, "to_block": 110, "chunk_size": 5},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "EVM_TRANSFER_INDEXER_LEASE_UNAVAILABLE"
