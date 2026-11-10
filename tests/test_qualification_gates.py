import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.qualification_gates import evaluate_qualification_gates


client = TestClient(app)

PASS_GATES = {
    "liquidity_pass": True,
    "data_quality_pass": True,
    "catalyst_quality_pass": True,
    "manipulation_risk_pass": True,
    "stop_loss_valid": True,
    "supply_risk_pass": True,
    "multi_timeframe_pass": True,
    "red_team_pass": True,
    "portfolio_risk_pass": True,
}


def test_qualification_gate_returns_buy_only_when_every_condition_passes():
    result = evaluate_qualification_gates(
        gates=PASS_GATES, net_risk_reward=2.1, timing_established=True,
        entry_conditions_met=True, final_audit_status="VALID",
    )
    assert result["decision"] == "BUY"
    assert result["status"] == "QUALIFIED"
    assert result["probability"] == "NOT_ESTABLISHED_BY_THIS_GATE_ENGINE"


def test_qualification_gate_never_passes_missing_or_pending_evidence():
    result = evaluate_qualification_gates(
        gates={"liquidity_pass": True}, net_risk_reward=None,
        timing_established=False, entry_conditions_met=False,
        final_audit_status="WAIT",
    )
    assert result["decision"] == "WAIT"
    assert result["missing_gates"]
    assert result["decision"] != "BUY"


@pytest.mark.parametrize("audit", ["EXPIRED", "INVALIDATED", "NO_TRADE"])
def test_qualification_gate_rejects_expired_invalidated_or_no_trade_audit(audit):
    result = evaluate_qualification_gates(
        gates=PASS_GATES, net_risk_reward=3.0, timing_established=True,
        entry_conditions_met=True, final_audit_status=audit,
    )
    assert result["decision"] == "NO TRADE"


def test_qualification_gate_rejects_failed_gate_and_rr_below_two():
    failed = dict(PASS_GATES)
    failed["liquidity_pass"] = False
    result = evaluate_qualification_gates(
        gates=failed, net_risk_reward=2.5, timing_established=True,
        entry_conditions_met=True, final_audit_status="VALID",
    )
    assert result["decision"] == "NO TRADE"
    result = evaluate_qualification_gates(
        gates=PASS_GATES, net_risk_reward=1.99, timing_established=True,
        entry_conditions_met=True, final_audit_status="VALID",
    )
    assert result["decision"] == "NO TRADE"


def test_qualification_gate_api():
    response = client.post("/api/v1/analysis/qualification-gates", json={
        "gates": PASS_GATES, "net_risk_reward": 2.0,
        "timing_established": True, "entry_conditions_met": True,
        "final_audit_status": "VALID",
    })
    assert response.status_code == 200
    assert response.json()["decision"] == "BUY"
