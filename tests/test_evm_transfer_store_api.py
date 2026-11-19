from fastapi.testclient import TestClient

from app import main
from app.main import app


client = TestClient(app)


class FakeProvider:
    async def chain_id(self):
        return 1


class FakeFlowStore:
    def __init__(self, complete):
        self.complete = complete

    def address_flow_summary(self, *args):
        return {
            "top_net_receivers": [],
            "top_net_senders": [],
            "warning": "Local indexed data only",
        }

    def history(self, chain_id, contract, from_block, to_block, limit):
        return []

    def range_coverage(self, chain_id, contract, from_block, to_block):
        return {
            "complete": self.complete,
            "requested_range": {"from": from_block, "to": to_block},
            "covered_through": to_block if self.complete else from_block,
            "gaps": [] if self.complete else [{"from": from_block + 1, "to": to_block}],
            "indexed_ranges": [(from_block, to_block)] if self.complete else [(from_block, from_block)],
        }


def _configure(monkeypatch, complete):
    monkeypatch.setattr(main, "get_evm_provider", lambda: FakeProvider())
    monkeypatch.setattr(main, "evm_transfer_store", FakeFlowStore(complete))
    monkeypatch.setattr(main.settings, "evm_wallet_registry", "[]")


def test_evm_history_flows_api_reports_incomplete_when_index_has_gaps(monkeypatch):
    _configure(monkeypatch, complete=False)
    response = client.get(
        f"/api/v1/onchain/evm/token/{'0x' + 'a' * 40}/history/flows",
        params={"from_block": 100, "to_block": 110, "decimals": 18},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "INCOMPLETE"
    assert body["indexed_coverage"]["complete"] is False
    assert body["indexed_coverage"]["gaps"] == [{"from": 101, "to": 110}]


def test_evm_history_flows_api_reports_completed_only_for_full_coverage(monkeypatch):
    _configure(monkeypatch, complete=True)
    response = client.get(
        f"/api/v1/onchain/evm/token/{'0x' + 'a' * 40}/history/flows",
        params={"from_block": 100, "to_block": 110, "decimals": 18},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "COMPLETED"
    assert body["indexed_coverage"]["complete"] is True
    assert body["indexed_coverage"]["gaps"] == []


def test_evm_history_api_reports_incomplete_when_index_has_gaps(monkeypatch):
    _configure(monkeypatch, complete=False)
    response = client.get(
        f"/api/v1/onchain/evm/token/{'0x' + 'a' * 40}/history",
        params={"from_block": 100, "to_block": 110},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "INCOMPLETE"
    assert body["indexed_coverage"]["complete"] is False
    assert body["indexed_coverage"]["gaps"] == [{"from": 101, "to": 110}]


def test_evm_history_api_reports_completed_only_for_full_coverage(monkeypatch):
    _configure(monkeypatch, complete=True)
    response = client.get(
        f"/api/v1/onchain/evm/token/{'0x' + 'a' * 40}/history",
        params={"from_block": 100, "to_block": 110},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "COMPLETED"
    assert body["indexed_coverage"]["complete"] is True
    assert body["indexed_coverage"]["gaps"] == []
