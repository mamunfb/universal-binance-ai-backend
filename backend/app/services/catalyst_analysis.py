from __future__ import annotations

import re
from typing import Any


CATALYST_RULES: list[tuple[str, tuple[str, ...], str, str, str, int]] = [
    ("HACK_EXPLOIT", ("hack", "exploit", "hacked", "security breach", "drained", "vulnerability"), "BEARISH", "HIGH", "SHORT_TERM", 5),
    ("DELISTING", ("delist", "delisting", "trading suspension", "suspend trading"), "BEARISH", "HIGH", "SHORT_TERM", 5),
    ("REGULATORY_ENFORCEMENT", ("lawsuit", "sec charges", "regulatory action", "ban", "sanction", "enforcement action"), "BEARISH", "HIGH", "SHORT_TO_MEDIUM_TERM", 5),
    ("TOKEN_UNLOCK", ("token unlock", "vesting", "unlock event", "cliff unlock"), "BEARISH", "MEDIUM", "EVENT_DEPENDENT", 4),
    ("LISTING", ("binance lists", "will list", "listing on", "new listing"), "BULLISH", "MEDIUM", "SHORT_TERM", 4),
    ("UPGRADE", ("mainnet upgrade", "network upgrade", "protocol upgrade", "hard fork", "software upgrade"), "MIXED", "MEDIUM", "MEDIUM_TERM", 3),
    ("PARTNERSHIP", ("partnership", "partners with", "strategic collaboration", "integrates with"), "MIXED", "LOW", "MEDIUM_TO_LONG_TERM", 2),
    ("FUNDING", ("raises", "raised", "funding round", "investment round", "series a", "series b"), "MIXED", "LOW", "MEDIUM_TO_LONG_TERM", 2),
    ("ETF_FLOW", ("etf inflow", "etf outflow", "spot etf", "etf approval"), "MIXED", "MEDIUM", "SHORT_TO_MEDIUM_TERM", 3),
    ("TOKEN_BURN", ("token burn", "burns tokens", "burn mechanism"), "MIXED", "LOW", "EVENT_DEPENDENT", 2),
    ("GOVERNANCE", ("governance proposal", "governance vote", "proposal passes", "dao vote"), "MIXED", "LOW", "EVENT_DEPENDENT", 2),
]

BULLISH_TERMS = ("surges", "soars", "record high", "beats estimates", "approved", "approval", "inflow", "accumulates")
BEARISH_TERMS = ("falls", "plunges", "crashes", "outflow", "sells", "selling pressure", "rejected", "denied")


def _classify(text: str) -> list[dict[str, Any]]:
    normalized = re.sub(r"[^a-z0-9]+", " ", text.lower())
    matches = []
    for kind, terms, direction, impact, horizon, weight in CATALYST_RULES:
        found = [term for term in terms if term in normalized]
        if found:
            matches.append({
                "type": kind,
                "matched_terms": found,
                "base_direction": direction,
                "impact_level": impact,
                "expected_horizon": horizon,
                "rule_weight": weight,
            })
    return matches


def analyze_catalysts(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Transparent keyword rules; outputs are triage labels, not price forecasts."""
    results = []
    for item in items:
        text = f"{item.get('title', '')} {item.get('summary') or ''}"
        matches = _classify(text)
        matched_terms = [term for match in matches for term in match["matched_terms"]]
        lowered = text.lower()
        bullish_hits = [term for term in BULLISH_TERMS if term in lowered]
        bearish_hits = [term for term in BEARISH_TERMS if term in lowered]
        directions = {match["base_direction"] for match in matches}
        if bullish_hits and not bearish_hits:
            direction = "BULLISH"
        elif bearish_hits and not bullish_hits:
            direction = "BEARISH"
        elif "LISTING" in {match["type"] for match in matches} and "BEARISH" not in directions:
            direction = "BULLISH"
        elif "BULLISH" in directions and "BEARISH" not in directions:
            direction = "BULLISH"
        elif "BEARISH" in directions and "BULLISH" not in directions:
            direction = "BEARISH"
        elif matches:
            direction = "MIXED"
        else:
            direction = "UNKNOWN"

        verification = item.get("verification_status", "UNVERIFIED")
        if not matches:
            catalyst_status = "NO_RULE_MATCH"
            score = None
        else:
            catalyst_status = "CANDIDATE"
            score = min(10, max(match["rule_weight"] for match in matches) + min(len(matches) - 1, 2))
        eligible_for_signal = verification == "CONFIRMED" and bool(matches) and direction in {"BULLISH", "BEARISH"}
        results.append({
            **item,
            "catalyst": {
                "status": catalyst_status,
                "types": [match["type"] for match in matches],
                "direction": direction,
                "impact_level": (
                    "HIGH" if any(match["impact_level"] == "HIGH" for match in matches) else
                    "MEDIUM" if any(match["impact_level"] == "MEDIUM" for match in matches) else
                    "LOW" if matches else "UNKNOWN"
                ),
                "expected_horizon": sorted({match["expected_horizon"] for match in matches}),
                "heuristic_score": score,
                "matched_terms": matched_terms,
                "bullish_context_terms": bullish_hits,
                "bearish_context_terms": bearish_hits,
                "verification_status": verification,
                "eligible_for_signal_review": eligible_for_signal,
                "limitations": (
                    "Keyword-rule triage only. It does not measure actual price impact, "
                    "causality, probability, or expected return. Confirm with market data."
                ),
            },
        })
    return results
