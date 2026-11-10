import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.trade_risk import build_trade_risk_plan


client = TestClient(app)


def test_spot_long_risk_plan_calculates_net_rr_and_position_size():
    result = build_trade_risk_plan(
        market="SPOT", direction="LONG", entry_price=100, stop_loss=95,
        take_profits=[110, 115], account_capital=1000, risk_percent=1,
        fee_rate_per_side=0.001, slippage_bps_per_side=5,
    )
    assert result["status"] == "COMPLETED"
    assert result["gross_risk_reward_ratios"] == [2.0, 3.0]
    assert result["net_risk_reward_ratios"][0] < 2.0
    assert result["risk_budget"]["risk_amount"] == 10
    assert result["risk_budget"]["position_units"] is not None
    assert result["liquidation_status"] == "NOT_APPLICABLE_TO_SPOT"


def test_usdm_short_requires_funding_cost_for_net_rr_and_withholds_liquidation():
    result = build_trade_risk_plan(
        market="USD_M", direction="SHORT", entry_price=100, stop_loss=105,
        take_profits=[90], account_capital=2000, risk_percent=0.5,
        fee_rate_per_side=0.0004, slippage_bps_per_side=3,
        adverse_funding_cost_percent=0.02,
    )
    assert result["status"] == "COMPLETED"
    assert result["net_risk_reward_ratios"][0] is not None
    assert result["liquidation_price"] is None
    assert "MAINTENANCE_TIER" in result["liquidation_status"]


def test_risk_plan_does_not_invent_net_rr_or_position_size_when_costs_missing():
    result = build_trade_risk_plan(
        market="SPOT", direction="LONG", entry_price=100, stop_loss=95,
        take_profits=[110], account_capital=1000, risk_percent=1,
    )
    assert result["status"] == "INCOMPLETE"
    assert result["net_risk_reward_ratios"] is None
    assert result["risk_budget"]["position_units"] is None
    assert result["cost_assumptions"]["net_rr_status"].startswith("NOT_ESTABLISHED")


def test_risk_plan_rejects_spot_short_and_coinm_inverse():
    with pytest.raises(ValueError):
        build_trade_risk_plan(market="SPOT", direction="SHORT", entry_price=100,
                              stop_loss=105, take_profits=[90])
    with pytest.raises(ValueError):
        build_trade_risk_plan(market="COIN_M", direction="LONG", entry_price=100,
                              stop_loss=95, take_profits=[110])


def test_trade_risk_plan_api_returns_user_supplied_calculation():
    response = client.post("/api/v1/analysis/trade-risk-plan", json={
        "market": "SPOT", "direction": "LONG", "entry_price": 100,
        "stop_loss": 95, "take_profits": [110],
        "fee_rate_per_side": 0.001, "slippage_bps_per_side": 5,
    })
    assert response.status_code == 200
    payload = response.json()
    assert payload["analysis_only"] is True
    assert payload["trading_enabled"] is False
    assert payload["gross_risk_reward_ratios"] == [2.0]
