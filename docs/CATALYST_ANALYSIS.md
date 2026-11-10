# Catalyst Analysis Engine — keyword triage stage

## What it does

The engine applies a transparent, editable keyword rule set to each ingested news item. It tags possible categories such as hack/exploit, delisting, regulatory enforcement, token unlock, listing, upgrade, partnership, funding, ETF-related event, token burn, and governance.

It returns:
- candidate catalyst type(s)
- heuristic direction: BULLISH, BEARISH, MIXED, or UNKNOWN
- coarse impact label: LOW, MEDIUM, HIGH, UNKNOWN
- broad expected horizon labels
- matched words and a transparent heuristic score (0–10)
- source verification status and signal-review eligibility

## Critical interpretation

This is keyword triage, not a language model fact-check, causal model, event study, or price-impact forecast. A keyword may be negated, quoted, or used in an unrelated context. An event's impact depends on expectations, token economics, timing, liquidity, and market conditions.

The score is a rule weight, NOT a probability, confidence percentage, expected return, or ranking validated against historical outcomes.

A catalyst is eligible for later signal review only when:
1. news verification status is CONFIRMED under the configured source-class heuristic;
2. at least one catalyst rule matched; and
3. the direction is unambiguously BULLISH or BEARISH.

Eligibility does not create a trade signal. Technical, liquidity, derivatives, risk/reward, and timestamp checks remain mandatory. No automatic BUY/SELL order is generated.

## Current categories

HACK_EXPLOIT, DELISTING, REGULATORY_ENFORCEMENT, TOKEN_UNLOCK, LISTING, UPGRADE, PARTNERSHIP, FUNDING, ETF_FLOW, TOKEN_BURN, GOVERNANCE.

The rule dictionary is intentionally conservative and should be expanded only with tests and labeled examples. The current direction labels are heuristic; some events are correctly MIXED because direction depends on context.
