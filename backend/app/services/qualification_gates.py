from __future__ import annotations

import math
from typing import Any


REQUIRED_GATES = (
    "liquidity_pass",
    "data_quality_pass",
    "catalyst_quality_pass",
    "manipulation_risk_pass",
    "stop_loss_valid",
    "supply_risk_pass",
    "multi_timeframe_pass",
    "red_team_pass",
    "portfolio_risk_pass",
)


def evaluate_qualification_gates(
    *,
    gates: dict[str, bool | None],
    net_risk_reward: float | None,
    timing_established: bool | None,
    entry_conditions_met: bool | None,
    final_audit_status: str,
) -> dict[str, Any]:
    """Strictly map supplied evidence gates to BUY/WAIT/NO TRADE; missing evidence never passes."""
    if not isinstance(gates, dict):
        raise ValueError("gates must be an object")
    audit = final_audit_status.strip().upper()
    if audit not in {"VALID", "WAIT", "EXPIRED", "INVALIDATED", "NO_TRADE"}:
        raise ValueError("final_audit_status must be VALID, WAIT, EXPIRED, INVALIDATED, or NO_TRADE")

    missing = [name for name in REQUIRED_GATES if name not in gates or gates[name] is None]
    invalid = [name for name in REQUIRED_GATES if gates.get(name) is False]
    rr_valid = (
        isinstance(net_risk_reward, (int, float))
        and not isinstance(net_risk_reward, bool)
        and math.isfinite(net_risk_reward)
        and net_risk_reward >= 2.0
    )
    if audit in {"EXPIRED", "INVALIDATED", "NO_TRADE"}:
        decision = "NO TRADE"
        reasons = [f"Final audit status is {audit}."]
    elif invalid or (net_risk_reward is not None and not rr_valid):
        decision = "NO TRADE"
        reasons = [f"Failed qualification gates: {invalid}"] if invalid else []
        if net_risk_reward is not None and not rr_valid:
            reasons.append("Net risk/reward is below 1:2 or invalid.")
    elif missing or net_risk_reward is None or timing_established is not True or entry_conditions_met is not True or audit != "VALID":
        decision = "WAIT"
        reasons = []
        if missing:
            reasons.append(f"Missing gate evidence: {missing}")
        if net_risk_reward is None:
            reasons.append("Net risk/reward is NOT ESTABLISHED.")
        if timing_established is not True:
            reasons.append("Entry timing is not established.")
        if entry_conditions_met is not True:
            reasons.append("Entry confirmation conditions are not all satisfied.")
        if audit == "WAIT":
            reasons.append("Final audit requires WAIT.")
    else:
        decision = "BUY"
        reasons = ["Every required gate passed, net risk/reward is at least 1:2, timing is established, entry conditions are met, and final audit is VALID."]

    return {
        "decision": decision,
        "status": "QUALIFIED" if decision == "BUY" else "REJECTED" if decision == "NO TRADE" else "PENDING_CONFIRMATION",
        "failed_gates": invalid,
        "missing_gates": missing,
        "net_risk_reward": net_risk_reward,
        "minimum_net_risk_reward": 2.0,
        "final_audit_status": audit,
        "reasons": reasons,
        "probability": "NOT_ESTABLISHED_BY_THIS_GATE_ENGINE",
        "risk_score": "NOT_CALCULATED_BY_THIS_GATE_ENGINE",
        "limitations": [
            "The caller must supply evidence-backed gate values; this function does not fetch or verify market data.",
            "A BUY result is only a rule-engine outcome for the supplied inputs, not a guarantee or financial advice.",
            "A missing or unknown gate never counts as a pass.",
        ],
    }
