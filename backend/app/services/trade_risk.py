from __future__ import annotations

import math
from typing import Any


def _positive(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a finite positive number")
    return float(value)


def build_trade_risk_plan(
    *,
    market: str,
    direction: str,
    entry_price: float,
    stop_loss: float,
    take_profits: list[float],
    account_capital: float | None = None,
    risk_percent: float | None = None,
    fee_rate_per_side: float | None = None,
    slippage_bps_per_side: float | None = None,
    adverse_funding_cost_percent: float | None = None,
    max_notional: float | None = None,
) -> dict[str, Any]:
    """Calculate transparent risk math; this does not validate a live setup or liquidation price."""
    normalized_market = market.strip().upper()
    normalized_direction = direction.strip().upper()
    if normalized_market not in {"SPOT", "USD_M"}:
        raise ValueError("Only SPOT and linear USD_M are supported; COIN_M inverse contracts are not implemented")
    if normalized_direction not in ({"LONG"} if normalized_market == "SPOT" else {"LONG", "SHORT"}):
        raise ValueError("SPOT supports LONG only; USD_M supports LONG or SHORT")
    entry = _positive(entry_price, "entry_price")
    stop = _positive(stop_loss, "stop_loss")
    if not isinstance(take_profits, list) or not 1 <= len(take_profits) <= 3:
        raise ValueError("take_profits must contain between one and three targets")
    targets = [_positive(value, "take_profit") for value in take_profits]
    if normalized_direction == "LONG":
        if not stop < entry or any(target <= entry for target in targets):
            raise ValueError("LONG requires stop_loss < entry_price < every take_profit")
        gross_risk = entry - stop
        gross_rewards = [target - entry for target in targets]
    else:
        if not stop > entry or any(target >= entry for target in targets):
            raise ValueError("SHORT requires every take_profit < entry_price < stop_loss")
        gross_risk = stop - entry
        gross_rewards = [entry - target for target in targets]

    capital = _positive(account_capital, "account_capital") if account_capital is not None else None
    risk_pct = _positive(risk_percent, "risk_percent") if risk_percent is not None else None
    if risk_pct is not None and risk_pct > 100:
        raise ValueError("risk_percent must not exceed 100")
    if (capital is None) != (risk_pct is None):
        raise ValueError("account_capital and risk_percent must be supplied together")
    fee = None if fee_rate_per_side is None else float(fee_rate_per_side)
    if fee is not None and (not math.isfinite(fee) or not 0 <= fee <= 0.05):
        raise ValueError("fee_rate_per_side must be between 0 and 0.05")
    slip = None if slippage_bps_per_side is None else float(slippage_bps_per_side)
    if slip is not None and (not math.isfinite(slip) or not 0 <= slip <= 500):
        raise ValueError("slippage_bps_per_side must be between 0 and 500")
    funding = None if adverse_funding_cost_percent is None else float(adverse_funding_cost_percent)
    if funding is not None and (not math.isfinite(funding) or not 0 <= funding <= 100):
        raise ValueError("adverse_funding_cost_percent must be between 0 and 100")

    costs_complete = fee is not None and slip is not None and (
        normalized_market == "SPOT" or funding is not None
    )
    cost_fraction = (fee + slip / 10000) if costs_complete else None
    funding_per_unit = entry * (funding / 100) if normalized_market == "USD_M" and funding is not None else 0.0
    net_risk_per_unit = (
        gross_risk + entry * cost_fraction + stop * cost_fraction + funding_per_unit
        if cost_fraction is not None else None
    )
    net_reward_per_unit = (
        [reward - entry * cost_fraction - target * cost_fraction - funding_per_unit for reward, target in zip(gross_rewards, targets)]
        if cost_fraction is not None else None
    )
    gross_rr = [reward / gross_risk for reward in gross_rewards]
    net_rr = (
        [reward / net_risk_per_unit if net_risk_per_unit and reward > 0 else None for reward in net_reward_per_unit]
        if net_reward_per_unit is not None else None
    )

    risk_amount = capital * risk_pct / 100 if capital is not None and risk_pct is not None else None
    position_units = risk_amount / net_risk_per_unit if risk_amount is not None and net_risk_per_unit else None
    sizing_basis = "NET_COST_ADJUSTED_RISK" if position_units is not None else "NOT_ESTABLISHED"
    notional = position_units * entry if position_units is not None else None
    if position_units is not None and normalized_market == "SPOT" and capital is not None:
        position_units = min(position_units, capital / entry)
        notional = position_units * entry
    if position_units is not None and max_notional is not None:
        cap = _positive(max_notional, "max_notional")
        position_units = min(position_units, cap / entry)
        notional = position_units * entry

    return {
        "status": "COMPLETED" if costs_complete else "INCOMPLETE",
        "market": normalized_market,
        "contract_model": "SPOT_CASH" if normalized_market == "SPOT" else "USD_M_LINEAR",
        "direction": normalized_direction,
        "entry_price": entry,
        "stop_loss": stop,
        "take_profits": targets,
        "gross_risk_per_unit": gross_risk,
        "gross_reward_per_unit": gross_rewards,
        "gross_risk_reward_ratios": gross_rr,
        "cost_assumptions": {
            "fee_rate_per_side": fee,
            "slippage_bps_per_side": slip,
            "adverse_funding_cost_percent": funding if normalized_market == "USD_M" else 0.0,
            "net_rr_status": "CALCULATED" if costs_complete else "NOT_ESTABLISHED_MISSING_COST_INPUTS",
        },
        "net_risk_per_unit": net_risk_per_unit,
        "net_reward_per_unit": net_reward_per_unit,
        "net_risk_reward_ratios": net_rr,
        "risk_budget": {
            "account_capital": capital,
            "risk_percent": risk_pct,
            "risk_amount": risk_amount,
            "position_units": position_units,
            "position_notional": notional,
            "sizing_basis": sizing_basis,
            "max_notional_cap": max_notional,
        },
        "liquidation_price": None,
        "liquidation_status": (
            "NOT_APPLICABLE_TO_SPOT" if normalized_market == "SPOT"
            else "NOT_ESTABLISHED_REQUIRES_MARGIN_MODE_AND_EXCHANGE_MAINTENANCE_TIER"
        ),
        "limitations": [
            "This is arithmetic for user-supplied levels and cost assumptions, not a market forecast or trade recommendation.",
            "No live price, order-book slippage simulation, exchange filter validation, or order execution is performed.",
            "USD_M liquidation price is withheld because leverage, margin mode, maintenance-margin tier and exchange bracket data are not supplied.",
            "COIN_M inverse contracts are not supported by this calculator.",
            "Position sizing is omitted unless both account_capital and risk_percent are supplied.",
        ],
    }
