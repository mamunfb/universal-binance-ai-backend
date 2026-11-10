from __future__ import annotations

import math
from typing import Any


def _positive(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a finite positive number")
    return float(value)


def _optional_cost(value: float | None, name: str, maximum: float) -> float | None:
    if value is None:
        return None
    number = float(value)
    if not math.isfinite(number) or not 0 <= number <= maximum:
        raise ValueError(f"{name} must be between 0 and {maximum}")
    return number


def _validate_budget(
    account_capital: float | None, risk_percent: float | None
) -> tuple[float | None, float | None, float | None]:
    capital = _positive(account_capital, "account_capital") if account_capital is not None else None
    risk_pct = _positive(risk_percent, "risk_percent") if risk_percent is not None else None
    if risk_pct is not None and risk_pct > 100:
        raise ValueError("risk_percent must not exceed 100")
    if (capital is None) != (risk_pct is None):
        raise ValueError("account_capital and risk_percent must be supplied together")
    risk_amount = capital * risk_pct / 100 if capital is not None and risk_pct is not None else None
    return capital, risk_pct, risk_amount


def _validate_levels(
    direction: str, entry_price: float, stop_loss: float, take_profits: list[float]
) -> tuple[float, float, list[float]]:
    entry = _positive(entry_price, "entry_price")
    stop = _positive(stop_loss, "stop_loss")
    if not isinstance(take_profits, list) or not 1 <= len(take_profits) <= 3:
        raise ValueError("take_profits must contain between one and three targets")
    targets = [_positive(value, "take_profit") for value in take_profits]
    if direction == "LONG":
        if not stop < entry or any(target <= entry for target in targets):
            raise ValueError("LONG requires stop_loss < entry_price < every take_profit")
    elif direction == "SHORT":
        if not stop > entry or any(target >= entry for target in targets):
            raise ValueError("SHORT requires every take_profit < entry_price < stop_loss")
    else:
        raise ValueError("direction must be LONG or SHORT")
    return entry, stop, targets


def _build_coinm_inverse_plan(
    *,
    direction: str,
    entry: float,
    stop: float,
    targets: list[float],
    contract_size_usd: float | None,
    settlement_asset: str | None,
    capital: float | None,
    risk_pct: float | None,
    risk_amount: float | None,
    fee: float | None,
    slip_bps: float | None,
    funding: float | None,
    max_notional: float | None,
) -> dict[str, Any]:
    """Calculate inverse COIN-M PnL in settlement coin for a fixed-USD-face-value contract."""
    if contract_size_usd is None:
        raise ValueError("contract_size_usd is required for COIN_M inverse contracts")
    face_value = _positive(contract_size_usd, "contract_size_usd")
    asset = (settlement_asset or "").strip().upper()
    if not asset or len(asset) > 20:
        raise ValueError("settlement_asset is required for COIN_M inverse contracts")
    if capital is not None and not (fee is not None and slip_bps is not None and funding is not None):
        # Keep position sizing unavailable when the total adverse cost model is incomplete.
        pass

    costs_complete = fee is not None and slip_bps is not None and funding is not None
    slip = slip_bps / 10000 if slip_bps is not None else None
    cost_rate = fee + slip if fee is not None and slip is not None else None

    def coin_pnl(exit_price: float) -> float:
        if direction == "LONG":
            return face_value * (1.0 / entry - 1.0 / exit_price)
        return face_value * (1.0 / exit_price - 1.0 / entry)

    gross_risk_coin = abs(coin_pnl(stop))
    gross_rewards_coin = [coin_pnl(target) for target in targets]
    gross_rr = [reward / gross_risk_coin for reward in gross_rewards_coin]

    entry_cost_coin = face_value / entry * cost_rate if cost_rate is not None else None
    stop_cost_coin = face_value / stop * cost_rate if cost_rate is not None else None
    target_costs_coin = (
        [face_value / target * cost_rate for target in targets]
        if cost_rate is not None else None
    )
    funding_cost_coin = (
        face_value / entry * (funding / 100)
        if funding is not None else None
    )
    net_risk_coin = (
        gross_risk_coin + entry_cost_coin + stop_cost_coin + funding_cost_coin
        if costs_complete else None
    )
    net_rewards_coin = (
        [
            reward - entry_cost_coin - target_cost - funding_cost_coin
            for reward, target_cost in zip(gross_rewards_coin, target_costs_coin)
        ]
        if costs_complete else None
    )
    net_rr = (
        [reward / net_risk_coin if net_risk_coin and reward > 0 else None for reward in net_rewards_coin]
        if net_rewards_coin is not None else None
    )

    contracts = (
        risk_amount / net_risk_coin
        if risk_amount is not None and net_risk_coin is not None and net_risk_coin > 0
        else None
    )
    notional = contracts * face_value if contracts is not None else None
    cap = _positive(max_notional, "max_notional") if max_notional is not None else None
    if contracts is not None and cap is not None and notional is not None and notional > cap:
        contracts = cap / face_value
        notional = cap

    return {
        "status": "COMPLETED" if costs_complete else "INCOMPLETE",
        "market": "COIN_M",
        "contract_model": "COIN_M_INVERSE_FIXED_USD_FACE_VALUE",
        "direction": direction,
        "entry_price": entry,
        "stop_loss": stop,
        "take_profits": targets,
        "contract_size_usd": face_value,
        "settlement_asset": asset,
        "pnl_unit": asset,
        "gross_risk_per_contract": gross_risk_coin,
        "gross_reward_per_contract": gross_rewards_coin,
        "gross_risk_reward_ratios": gross_rr,
        "cost_assumptions": {
            "fee_rate_per_side": fee,
            "slippage_bps_per_side": slip_bps,
            "adverse_funding_cost_percent": funding,
            "funding_interpretation": "Total adverse funding cost as a percentage of entry USD notional over the planned holding period.",
            "net_rr_status": "CALCULATED" if costs_complete else "NOT_ESTABLISHED_MISSING_COST_INPUTS",
        },
        "net_risk_per_contract": net_risk_coin,
        "net_reward_per_contract": net_rewards_coin,
        "net_risk_reward_ratios": net_rr,
        "risk_budget": {
            "account_capital": capital,
            "account_capital_unit": asset,
            "risk_percent": risk_pct,
            "risk_amount": risk_amount,
            "risk_amount_unit": asset,
            "position_units": contracts,
            "position_unit": "CONTRACTS",
            "position_notional_usd": notional,
            "sizing_basis": "INVERSE_COIN_PNL_NET_COST_ADJUSTED" if contracts is not None else "NOT_ESTABLISHED",
            "max_notional_cap_usd": cap,
        },
        "liquidation_price": None,
        "liquidation_status": "NOT_ESTABLISHED_REQUIRES_LEVERAGE_MARGIN_MODE_AND_EXCHANGE_MAINTENANCE_TIER",
        "limitations": [
            "COIN-M PnL is calculated in the declared settlement asset using the inverse fixed-USD-face-value formula.",
            "account_capital and risk_percent sizing require account_capital to be denominated in settlement_asset.",
            "Funding input is the total adverse funding percentage over the planned holding period, not one funding interval.",
            "Contract quantity step size, minimum quantity/notional, leverage brackets, margin mode and liquidation price are not validated here.",
            "Fees and slippage are user-supplied assumptions; no live order-book simulation or execution is performed.",
            "This arithmetic does not validate a live setup, forecast a price, or place an order.",
        ],
    }


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
    contract_size_usd: float | None = None,
    settlement_asset: str | None = None,
) -> dict[str, Any]:
    """Calculate transparent Spot, linear USD-M, or inverse COIN-M risk arithmetic."""
    normalized_market = market.strip().upper()
    normalized_direction = direction.strip().upper()
    if normalized_market not in {"SPOT", "USD_M", "COIN_M"}:
        raise ValueError("market must be SPOT, USD_M, or COIN_M")
    if normalized_market == "SPOT" and normalized_direction != "LONG":
        raise ValueError("SPOT supports LONG only")
    if normalized_market in {"USD_M", "COIN_M"} and normalized_direction not in {"LONG", "SHORT"}:
        raise ValueError("Futures supports LONG or SHORT")

    entry, stop, targets = _validate_levels(
        normalized_direction, entry_price, stop_loss, take_profits
    )
    capital, risk_pct, risk_amount = _validate_budget(account_capital, risk_percent)
    fee = _optional_cost(fee_rate_per_side, "fee_rate_per_side", 0.05)
    slip_bps = _optional_cost(slippage_bps_per_side, "slippage_bps_per_side", 500)
    funding = _optional_cost(adverse_funding_cost_percent, "adverse_funding_cost_percent", 100)

    if normalized_market == "COIN_M":
        return _build_coinm_inverse_plan(
            direction=normalized_direction,
            entry=entry,
            stop=stop,
            targets=targets,
            contract_size_usd=contract_size_usd,
            settlement_asset=settlement_asset,
            capital=capital,
            risk_pct=risk_pct,
            risk_amount=risk_amount,
            fee=fee,
            slip_bps=slip_bps,
            funding=funding,
            max_notional=max_notional,
        )

    if contract_size_usd is not None or settlement_asset is not None:
        raise ValueError("contract_size_usd and settlement_asset are only valid for COIN_M")

    if normalized_market == "LONG":
        gross_risk = entry - stop
        gross_rewards = [target - entry for target in targets]
    else:
        gross_risk = stop - entry
        gross_rewards = [entry - target for target in targets]

    costs_complete = fee is not None and slip_bps is not None and (
        normalized_market == "SPOT" or funding is not None
    )
    cost_fraction = (fee + slip_bps / 10000) if costs_complete else None
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

    position_units = risk_amount / net_risk_per_unit if risk_amount is not None and net_risk_per_unit else None
    sizing_basis = "NET_COST_ADJUSTED_RISK" if position_units is not None else "NOT_ESTABLISHED"
    notional = position_units * entry if position_units is not None else None
    if position_units is not None and normalized_market == "SPOT" and capital is not None:
        position_units = min(position_units, capital / entry)
        notional = position_units * entry
    cap = _positive(max_notional, "max_notional") if max_notional is not None else None
    if position_units is not None and cap is not None:
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
            "slippage_bps_per_side": slip_bps,
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
            "max_notional_cap": cap,
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
            "Position sizing is omitted unless both account_capital and risk_percent are supplied.",
        ],
    }
