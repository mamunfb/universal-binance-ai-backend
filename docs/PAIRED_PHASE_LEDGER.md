# Paired SPOT / FUTURES Phase Ledger

Last updated: 2026-11-11
Repository: mamunfb/universal-binance-ai-backend
Work branch: work/dual-master-prompt-audit
Governing specifications:
- `master-prompts/MASTER_PROMPT_01_SPOT.md`
- `master-prompts/MASTER_PROMPT_02_FUTURES.md`
- `docs/UNIVERSAL_PROJECT_SCOPE_AND_EXECUTION_CONTROL.md`

## Status vocabulary

- `NOT_STARTED`: no implementation work accepted for this phase.
- `IN_PROGRESS`: work exists but one or more requirements/evidence/acceptance checks remain incomplete.
- `BLOCKED`: a documented blocker prevents safe continuation.
- `COMPLETE`: every market-specific requirement, integration, normal/failure/partial/missing-data test, data coverage check and acceptance evidence has passed.

A paired Phase N is complete only when both SPOT Phase N and FUTURES Phase N are `COMPLETE`. Phase N+1 remains locked otherwise. No phase may be skipped, merged or pre-implemented.

## Current paired ledger

| Phase | SPOT | FUTURES | Combined gate |
|---|---|---|---|
| 01 — Complete Binance Market Scanner | IN_PROGRESS | IN_PROGRESS | INCOMPLETE |
| 02 — Global Crypto News Intelligence | NOT_STARTED | NOT_STARTED | LOCKED |
| 03 — News Verification & Catalyst Analysis | NOT_STARTED | NOT_STARTED | LOCKED |
| 04 — Initial Coin Filtering | NOT_STARTED | NOT_STARTED | LOCKED |
| 05 — Bitcoin & Global Market Analysis | NOT_STARTED | NOT_STARTED | LOCKED |
| 06 — Deep Technical Analysis | NOT_STARTED | NOT_STARTED | LOCKED |
| 07 — Liquidity / Derivatives & Microstructure | NOT_STARTED | NOT_STARTED | LOCKED |
| 08 — On-Chain Intelligence | NOT_STARTED | NOT_STARTED | LOCKED |
| 09 — Tokenomics & Fundamental Analysis | NOT_STARTED | NOT_STARTED | LOCKED |
| 10 — Whale & Smart Money Tracking | NOT_STARTED | NOT_STARTED | LOCKED |
| 11 — Exchange Fund Flow Analysis | NOT_STARTED | NOT_STARTED | LOCKED |
| 12 — Market Manipulation Detection | NOT_STARTED | NOT_STARTED | LOCKED |
| 13 — Multi-Timeframe Confirmation | NOT_STARTED | NOT_STARTED | LOCKED |
| 14 — Historical Performance Validation | NOT_STARTED | NOT_STARTED | LOCKED |
| 15 — AI Probability & Forecasting | NOT_STARTED | NOT_STARTED | LOCKED |
| 16 — Risk Management & Exact Trade Timing | NOT_STARTED | NOT_STARTED | LOCKED |
| 17 — Final Coin Selection & Ranking | NOT_STARTED | NOT_STARTED | LOCKED |
| 18 — Independent AI Red-Team Review | NOT_STARTED | NOT_STARTED | LOCKED |
| 19 — Final Signal Audit & Entry Window Validation | NOT_STARTED | NOT_STARTED | LOCKED |
| 20 — Final Professional Report & Decision | NOT_STARTED | NOT_STARTED | LOCKED |

## Phase 01 acceptance blockers

### SPOT
- Complete all-eligible-pair Stage 1 coverage, with explicit per-symbol success/failure reasons.
- Complete order-book depth for every eligible pair or exact unavailable/failure accounting.
- Recent-average volume surge and volatility/activity measurements.
- Market-cap enrichment with source, retrieval timestamp and units.
- Risk-label, monitoring/seed-tag and delisting-status evidence.
- Objective Top Gainers, Top Losers, highest-volume, unusual-activity and initial-candidate outputs.
- Source-specific retrieval timestamps, freshness and API rate-limit/failure evidence.

### FUTURES
- Complete USDⓈ-M and COIN-M active perpetual and dated contract accounting.
- Per-contract success/failure reasons and missing-data ledger.
- Full contract order-book depth or exact unavailable/failure accounting.
- Recent-average volume surge, relative strength versus BTC, market-cap enrichment.
- Per-contract Open Interest and change where supported; explicit unavailable reasons where not.
- Funding/basis units, COIN-M volume derivation provenance and source-specific timestamps.
- Risk-label, monitoring/seed-tag and delisting/settlement status evidence.
- Objective Top Gainers, Top Losers, highest-volume, unusual-activity and initial-candidate outputs.

## Audit and verification gate

- Pre-Coding Full Audit: INCOMPLETE.
- No new Phase 01 feature coding is authorized until the remaining audit coverage and latest CI/static-check results are reviewed.
- Confirmed fixes and their regression evidence are maintained in `docs/MASTER_PROMPT_IMPLEMENTATION_AUDIT.md`.
- Latest successful CI evidence before the most recent combined security fixes: 527 passed, 2 warnings at commit `f35e8a777c46cbc6e0bc6e840e4b81597a17318b`.
- Latest combined security-fix tests and core Ruff check: PASSED at commit `dcfb8faf5372c0a9f75088d9e7f79afb9b2c42c7`; 528 tests passed, 2 warnings.
- Local working-tree status: UNVERIFIED through the remote GitHub interface.
- PR #1: OPEN / DRAFT; do not merge without explicit user approval.
- Main branch: unchanged.

## Continuity

Resume by completing the pre-coding audit gate, review current CI and static-analysis results, fix confirmed current-scope defects, and only then implement SPOT Phase 01. After SPOT Phase 01 acceptance, implement FUTURES Phase 01. Do not start Phase 02 until both Phase 01 statuses are COMPLETE.
