from __future__ import annotations

from typing import Any


def _direction(value: Any) -> str | None:
    if value in {"BULLISH", "BUY", "UP", "ALL_TIMEFRAMES_BUY_CVD"}:
        return "BULLISH"
    if value in {"BEARISH", "SELL", "DOWN", "ALL_TIMEFRAMES_SELL_CVD"}:
        return "BEARISH"
    return None


def analyze_market_structure_confluence(
    market: str, symbol: str, interval: str,
    structure: dict[str, Any], market_regime: dict[str, Any],
    order_flow: dict[str, Any], multi_timeframe_flow: dict[str, Any],
    liquidity_sweep: dict[str, Any],
) -> dict[str, Any]:
    """Summarize agreement/conflict across independent descriptive analysis outputs."""
    normalized_market, normalized_symbol = market.upper(), symbol.upper()
    evidence: list[dict[str, Any]] = []

    structure_dir = _direction(structure.get("structure"))
    break_data = structure.get("structure_break") or {}
    break_dir = _direction(break_data.get("direction"))
    evidence.append({
        "source": "MARKET_STRUCTURE",
        "status": structure.get("status"),
        "direction": structure_dir,
        "detail": {
            "classification": structure.get("structure"),
            "current_close": structure.get("current_close"),
            "latest_swing_high": (structure.get("swing_points") or {}).get("latest_high"),
            "latest_swing_low": (structure.get("swing_points") or {}).get("latest_low"),
        },
    })
    evidence.append({
        "source": "STRUCTURE_BREAK",
        "status": "CONFIRMED_BY_CLOSE" if break_data.get("confirmed_by_close") else break_data.get("type"),
        "direction": break_dir,
        "detail": {
            "type": break_data.get("type"),
            "broken_level": break_data.get("broken_level"),
            "confirmed_by_close": break_data.get("confirmed_by_close"),
        },
    })

    regime_dir = _direction((market_regime.get("directional_context")))
    evidence.append({
        "source": "MARKET_REGIME",
        "status": market_regime.get("status"),
        "direction": regime_dir,
        "detail": {
            "regime": market_regime.get("market_regime"),
            "volatility_regime": market_regime.get("volatility_regime"),
            "structure_regime": market_regime.get("structure_regime"),
            "metrics": market_regime.get("metrics"),
        },
    })

    flow_dir = None
    flow = order_flow.get("aggressor_flow") or {}
    cvd = flow.get("net_cvd_quantity")
    if isinstance(cvd, (int, float)) and cvd > 0:
        flow_dir = "BULLISH"
    elif isinstance(cvd, (int, float)) and cvd < 0:
        flow_dir = "BEARISH"
    evidence.append({
        "source": "ORDER_FLOW_CVD",
        "status": order_flow.get("status"),
        "direction": flow_dir,
        "detail": {
            "net_cvd_quantity": cvd,
            "trade_count": order_flow.get("trade_count"),
            "divergence": (order_flow.get("price_cvd_divergence") or {}).get("classification"),
            "poc": (order_flow.get("volume_profile") or {}).get("poc"),
            "value_area": (order_flow.get("volume_profile") or {}).get("value_area"),
            "coverage": order_flow.get("coverage"),
        },
    })

    mtf_dir = _direction(multi_timeframe_flow.get("cvd_agreement"))
    evidence.append({
        "source": "MULTI_TIMEFRAME_CVD",
        "status": multi_timeframe_flow.get("status"),
        "direction": mtf_dir,
        "detail": {
            "cvd_agreement": multi_timeframe_flow.get("cvd_agreement"),
            "completed_timeframe_count": multi_timeframe_flow.get("completed_timeframe_count"),
            "timeframe_count": multi_timeframe_flow.get("timeframe_count"),
            "timeframes": [
                {
                    "period": item.get("period"),
                    "status": item.get("status"),
                    "net_cvd_quantity": item.get("net_cvd_quantity"),
                    "price_cvd_divergence": item.get("price_cvd_divergence"),
                    "poc": item.get("poc"),
                    "value_area": item.get("value_area"),
                    "coverage": item.get("coverage"),
                }
                for item in (multi_timeframe_flow.get("timeframes") or [])
            ],
        },
    })

    sweep_candidates = liquidity_sweep.get("sweep_candidates") or []
    latest_sweep = sweep_candidates[0] if sweep_candidates else None
    sweep_dir = None
    if latest_sweep:
        sweep_dir = (
            "BULLISH" if latest_sweep.get("direction") == "BULLISH_AFTER_SELL_SIDE_SWEEP"
            else "BEARISH" if latest_sweep.get("direction") == "BEARISH_AFTER_BUY_SIDE_SWEEP"
            else None
        )
    evidence.append({
        "source": "LIQUIDITY_SWEEP",
        "status": latest_sweep.get("confirmation_status") if latest_sweep else liquidity_sweep.get("status"),
        "direction": sweep_dir,
        "detail": {
            "sweep_type": latest_sweep.get("sweep_type") if latest_sweep else None,
            "sweep_time_ms": latest_sweep.get("sweep_time_ms") if latest_sweep else None,
            "evidence_count": latest_sweep.get("evidence_count") if latest_sweep else 0,
            "aggressor_flow": latest_sweep.get("aggressor_flow") if latest_sweep else None,
            "volume_profile": latest_sweep.get("volume_profile") if latest_sweep else None,
            "order_book_context": latest_sweep.get("order_book_context") if latest_sweep else None,
            "derivatives_context": latest_sweep.get("derivatives_context") if latest_sweep else None,
        },
    })

    usable = [item for item in evidence if item["direction"] in {"BULLISH", "BEARISH"}]
    bullish = sum(item["direction"] == "BULLISH" for item in usable)
    bearish = sum(item["direction"] == "BEARISH" for item in usable)
    conflicts = [
        item["source"] for item in usable
        if (bullish > 0 and bearish > 0)
    ]
    if not usable:
        alignment = "INSUFFICIENT_DIRECTIONAL_EVIDENCE"
        bias = "UNKNOWN"
    elif bullish and bearish:
        alignment = "CONFLICTING_EVIDENCE"
        bias = "MIXED"
    elif bullish:
        alignment = "BULLISH_EVIDENCE_ALIGNMENT"
        bias = "BULLISH"
    else:
        alignment = "BEARISH_EVIDENCE_ALIGNMENT"
        bias = "BEARISH"

    valid_sources = sum(
        item.get("status") in {"COMPLETED", "MULTI_SOURCE_CANDIDATE", "SINGLE_SOURCE_CANDIDATE", "OHLC_ONLY_CANDIDATE", "CONFIRMED_BY_CLOSE"}
        for item in evidence
    )
    return {
        "status": "COMPLETED" if valid_sources else "INSUFFICIENT_DATA",
        "market": normalized_market, "symbol": normalized_symbol,
        "interval": interval,
        "confluence": {
            "bias": bias,
            "alignment": alignment,
            "bullish_evidence_count": bullish,
            "bearish_evidence_count": bearish,
            "directional_source_count": len(usable),
            "available_source_count": valid_sources,
            "total_source_count": len(evidence),
            "conflicting_sources": conflicts,
            "is_prediction": False,
        },
        "evidence": evidence,
        "source_status": {
            "market_structure": structure.get("status"),
            "market_regime": market_regime.get("status"),
            "order_flow": order_flow.get("status"),
            "multi_timeframe_order_flow": multi_timeframe_flow.get("status"),
            "liquidity_sweep": liquidity_sweep.get("status"),
        },
        "interpretation": (
            "Alignment means only that the supplied descriptive heuristics point in the same direction. "
            "It is not a probability, independent statistical confirmation, or a trading signal."
        ),
        "limitations": [
            "Inputs are local-history analyses with potentially incomplete candle, trade and order-book coverage.",
            "Market structure and regime are fixed heuristics; their labels are not predictive or statistically calibrated.",
            "CVD is aggressor-side volume from locally captured aggregate trades and does not identify participants.",
            "Multi-timeframe windows overlap; their agreement is not independent confirmation.",
            "Liquidity sweeps are OHLC wick/reclaim candidates, not proof of triggered stops.",
            "A missing or neutral source contributes no directional vote; it is not treated as evidence for the opposite side.",
            "The engine does not calculate win probability, entry, stop, target, leverage, or investment advice.",
        ],
    }
