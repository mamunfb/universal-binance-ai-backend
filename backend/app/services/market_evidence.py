from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _section_status(section: Any) -> str:
    return section.get("status", "UNKNOWN") if isinstance(section, dict) else "UNKNOWN"


def build_market_evidence_snapshot(
    symbol: str,
    multi_timeframe: dict[str, Any],
    spot_futures_basis: dict[str, Any],
    derivatives: dict[str, Any],
    volume_structure: dict[str, Any],
    catalysts: dict[str, Any],
) -> dict[str, Any]:
    """Summarize observed evidence without producing a trade signal or probability."""
    sections = {
        "multi_timeframe": multi_timeframe,
        "spot_futures_basis": spot_futures_basis,
        "derivatives": derivatives,
        "volume_structure": volume_structure,
        "news_catalysts": catalysts,
    }
    evidence: list[dict[str, Any]] = []
    limitations: list[str] = []

    timeframes = multi_timeframe.get("timeframes", {})
    if _section_status(multi_timeframe) == "COMPLETED":
        daily = timeframes.get("1d", {}).get("trend_structure", "UNKNOWN")
        four_hour = timeframes.get("4h", {}).get("trend_structure", "UNKNOWN")
        evidence.append({
            "category": "TREND_ALIGNMENT",
            "status": "OBSERVED",
            "timeframes": ["4h", "1d"],
            "observations": {"4h": four_hour, "1d": daily},
            "direction": (
                "BULLISH" if daily == four_hour == "BULLISH_STRUCTURE" else
                "BEARISH" if daily == four_hour == "BEARISH_STRUCTURE" else
                "MIXED_OR_UNKNOWN"
            ),
            "source": "Binance Spot klines",
        })
    else:
        limitations.append("Multi-timeframe Spot data is incomplete.")

    comparison = spot_futures_basis.get("price_comparison", {})
    if _section_status(comparison) == "COMPLETED":
        evidence.append({
            "category": "SPOT_FUTURES_BASIS",
            "status": "OBSERVED",
            "basis": comparison.get("basis"),
            "basis_percent": comparison.get("basis_percent"),
            "relationship": comparison.get("relationship"),
            "source": spot_futures_basis.get("source", "Binance Spot and USD-M Futures"),
        })
    else:
        limitations.append("Spot/Futures price comparison is unavailable or incomplete.")

    funding = spot_futures_basis.get("funding", {})
    if _section_status(funding) == "COMPLETED":
        rate = funding.get("funding_rate")
        evidence.append({
            "category": "FUNDING_RATE",
            "status": "OBSERVED",
            "funding_rate": rate,
            "funding_time_ms": funding.get("funding_time_ms"),
            "sign": "POSITIVE" if isinstance(rate, (int, float)) and rate > 0 else
                    "NEGATIVE" if isinstance(rate, (int, float)) and rate < 0 else "ZERO_OR_UNCLASSIFIED",
            "source": funding.get("source"),
        })
    else:
        limitations.append("Funding-rate evidence is unavailable.")

    derivative_sections = derivatives.get("sections", {})
    for key, label, field in (
        ("open_interest", "OPEN_INTEREST", "openInterest"),
        ("global_long_short_account_ratio", "GLOBAL_ACCOUNT_RATIO", "longShortRatio"),
        ("taker_buy_sell_ratio", "TAKER_BUY_SELL_RATIO", "buySellRatio"),
    ):
        section = derivative_sections.get(key, {})
        if _section_status(section) == "COMPLETED":
            data = section.get("data")
            if isinstance(data, list):
                data = data[-1] if data else None
            value = data.get(field) if isinstance(data, dict) else (
                data if isinstance(data, (int, float, str)) else None
            )
            evidence.append({
                "category": label,
                "status": "OBSERVED" if value is not None else "INCOMPLETE",
                "value": value,
                "source": derivatives.get("source"),
            })
        else:
            limitations.append(f"{label} data is unavailable.")

    oi_history = derivative_sections.get("open_interest_history", {})
    history_rows = oi_history.get("data") if isinstance(oi_history, dict) else None
    if _section_status(oi_history) == "COMPLETED" and isinstance(history_rows, list) and len(history_rows) >= 2:
        try:
            first_oi = float(history_rows[0]["sumOpenInterest"])
            latest_oi = float(history_rows[-1]["sumOpenInterest"])
            first_time = history_rows[0].get("timestamp")
            latest_time = history_rows[-1].get("timestamp")
            import math
            valid_oi = (
                math.isfinite(first_oi) and math.isfinite(latest_oi)
                and first_oi > 0 and latest_oi > 0
            )
        except (KeyError, TypeError, ValueError, OverflowError):
            valid_oi = False
        if valid_oi:
            evidence.append({
                "category": "OPEN_INTEREST_HISTORY",
                "status": "OBSERVED",
                "first_value": first_oi,
                "latest_value": latest_oi,
                "change_percent": (latest_oi - first_oi) / first_oi * 100,
                "first_timestamp_ms": first_time,
                "latest_timestamp_ms": latest_time,
                "source": derivatives.get("source"),
                "warning": "Open-interest change alone does not identify long or short positioning.",
            })
        else:
            limitations.append("Open-interest history contains invalid values.")
    else:
        limitations.append("Open-interest history coverage is insufficient for a change calculation.")

    order_book = derivative_sections.get("order_book", {})
    order_data = order_book.get("data", {}) if isinstance(order_book, dict) else {}
    if _section_status(order_book) == "COMPLETED" and _section_status(order_data) == "COMPLETED":
        evidence.append({
            "category": "ORDER_BOOK_DEPTH",
            "status": "OBSERVED",
            "depth_imbalance": order_data.get("depth_imbalance"),
            "spread_bps": order_data.get("spread_bps"),
            "source": derivatives.get("source"),
            "warning": "Snapshot liquidity can change rapidly and is not proof of intent.",
        })
    else:
        limitations.append("Order-book snapshot is unavailable or invalid.")

    if _section_status(volume_structure) == "COMPLETED":
        vwap = volume_structure.get("vwap", {})
        profile = volume_structure.get("volume_profile", {})
        structure = volume_structure.get("market_structure", {})
        evidence.append({
            "category": "VOLUME_AND_STRUCTURE",
            "status": "OBSERVED",
            "latest_vwap": vwap.get("latest_vwap"),
            "latest_close": vwap.get("latest_close"),
            "poc": profile.get("poc", {}).get("price_mid") if isinstance(profile.get("poc"), dict) else None,
            "vah": profile.get("vah"),
            "val": profile.get("val"),
            "trend_state": structure.get("trend_state"),
            "source": volume_structure.get("source"),
            "method_warning": volume_structure.get("warning"),
        })
    else:
        limitations.append("Volume/market-structure analysis is incomplete.")

    news_items = catalysts.get("items", [])
    confirmed = [
        item for item in news_items
        if item.get("verification_status") == "CONFIRMED"
        and item.get("catalyst", {}).get("eligible_for_signal_review") is True
    ]
    evidence.append({
        "category": "NEWS_CATALYSTS",
        "status": (
            "INCOMPLETE" if _section_status(catalysts) != "COMPLETED" else
            "OBSERVED" if confirmed else "NO_CONFIRMED_CANDIDATES"
        ),
        "confirmed_signal_review_candidates": len(confirmed),
        "candidates": [
            {
                "title": item.get("title"),
                "url": item.get("url"),
                "published_at": item.get("published_at"),
                "direction": item.get("catalyst", {}).get("direction"),
                "types": item.get("catalyst", {}).get("types"),
                "verification_status": item.get("verification_status"),
            }
            for item in confirmed[:10]
        ],
        "source_status": catalysts.get("status"),
    })
    if _section_status(catalysts) != "COMPLETED":
        limitations.append("Configured news-feed coverage is incomplete.")

    derivative_required = (
        "open_interest", "open_interest_history",
        "global_long_short_account_ratio", "taker_buy_sell_ratio", "order_book",
    )
    derivative_sections_complete = all(
        _section_status(derivative_sections.get(key)) == "COMPLETED"
        for key in derivative_required
    )
    if _section_status(derivatives) != "COMPLETED" or not derivative_sections_complete:
        limitations.append("One or more required USD-M derivatives sections are missing or incomplete.")

    section_status = {name: _section_status(value) for name, value in sections.items()}
    if not derivative_sections_complete:
        section_status["derivatives"] = "INCOMPLETE"
    statuses = list(section_status.values())
    overall = "COMPLETED" if all(value == "COMPLETED" for value in statuses) else "INCOMPLETE"
    return {
        "status": overall,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "symbol": symbol.upper(),
        "mode": "RESEARCH_ONLY_EVIDENCE_SUMMARY",
        "section_status": section_status,
        "evidence": evidence,
        "limitations": limitations,
        "decision": {
            "status": "NO_TRADE_DECISION",
            "buy_sell_signal": None,
            "probability": None,
            "reason": "This endpoint summarizes evidence only; it does not calculate a validated forecast, probability, or trading recommendation.",
        },
        "warnings": [
            "Evidence sources may have different timestamps and are not an atomic market snapshot.",
            "Keyword-based news verification and catalyst classification are heuristic triage, not proof of truth or price impact.",
            "OHLCV volume profile is an approximation, not trade-level volume-at-price.",
            "No single observed metric should be interpreted as a standalone trading signal.",
        ],
    }
