# UNIVERSAL BINANCE AI BACKEND — COMPLETE PROJECT SCOPE & EXECUTION CONTROL

Version: 1.0
Status: ACTIVE — Phase 01 paired gate is the only authorized implementation phase.
Repository: mamunfb/universal-binance-ai-backend
Canonical specifications:
- master-prompts/MASTER_PROMPT_01_SPOT.md (Master Prompt 01 — SPOT)
- master-prompts/MASTER_PROMPT_02_FUTURES.md (Master Prompt 02 — FUTURES)

## 1. Authority and precedence

This document is the repository-wide project scope, work breakdown, sequencing contract, acceptance framework and restart checkpoint. The two canonical master prompts above remain the detailed functional specifications. Neither this document nor a future implementation may shorten, replace, reinterpret or silently override them.

For every requirement, preserve the market-specific distinction:
- SPOT prompt governs Spot market research and Spot-long-only planning.
- FUTURES prompt governs Futures research, including USD-M and COIN-M distinctions, contract mechanics, funding, open interest, leverage and liquidation constraints.
- Shared infrastructure is permitted only where it is market-neutral. Shared code must not merge Spot and Futures calculations, units, market rules or outputs.

The system is research-only. No order placement, cancellation, modification, withdrawals, wallet signing or trading permission is allowed.

## 2. Full project scope — work from first heading to final closure

The implementation scope includes every applicable requirement in ALL sections of BOTH canonical prompts, not just the 20 numbered phases.

### 2.1 System identity and mission
Build an institutional-grade, evidence-led crypto market research and decision-support backend. It must scan the full eligible Binance market, research and verify candidate-specific catalysts, run market-specific quantitative and qualitative analysis, evaluate uncertainty and risk, and produce conditional BUY / WAIT / NO TRADE decisions only when supported by evidence. It must never force a trade or fabricate data, sources, probabilities, dates or times.

### 2.2 User configuration and market universe
Implement the user-configurable settings and defaults specified in each prompt, including market selection, eligible universe, direction rules, timeframes, forecast horizons, timezone, optional account/risk inputs, qualification gates, risk/ranking methodology, freshness limits, screening funnel, signal validity, portfolio risk and output language.
- Full dynamic universe; no fixed scan cap.
- Exact total / eligible / scanned / failed / excluded accounting.
- Duplicate base/underlying consolidation without comparing unlike quote, margin or settlement units.
- Configurable user inputs must remain optional where the prompt says optional; never invent missing account settings.

### 2.3 Six global mandatory rules
All phases and all persisted outputs must enforce:
1. Live data is mandatory for live conclusions; identify source and retrieval time.
2. No fabricated probabilities; distinguish statistical probability, model forecast, qualitative confidence and risk score.
3. News source is mandatory; retain direct URL, publisher, publication/event times and verification status.
4. NO TRADE / WAIT remains valid; never force candidates.
5. Timestamp every phase and dataset with BST default and UTC traceability as applicable.
6. Data integrity and missing-data protection; no silent skips, substitutions or unsupported certainty.

### 2.4 Binance API integration architecture
Implement and maintain official Binance API integrations applicable to each prompt, using current official documentation for endpoint contracts, filters, rate limits and response semantics. Include secure configuration, public endpoint preference, least privilege, no secrets in source/logs/reports, batching, pagination, caching, validation, retries/timeouts, freshness detection, endpoint-level accounting and explicit unavailable-data records. Spot and Futures adapters remain separate. A prompt alone is not a data connection; deployment capabilities must be checked.

### 2.5 Complete 20-phase analysis engine — paired execution
Every numbered phase below is a two-part deliverable: finish SPOT Phase N, then FUTURES Phase N, verify both, and only then unlock Phase N+1. The exact task lists, subheadings and outputs under the corresponding phase in each canonical prompt are mandatory and controlling.

| Phase | SPOT deliverable | FUTURES deliverable |
|---|---|---|
| 01 | Complete Binance Spot Market Scanner | Complete Binance Futures Market Scanner (USD-M and COIN-M as specified) |
| 02 | Global Crypto News Intelligence | Global Crypto News Intelligence |
| 03 | News Verification & Catalyst Analysis | News Verification & Catalyst Analysis |
| 04 | Initial Coin Filtering | Initial Coin Filtering |
| 05 | Bitcoin & Global Market Analysis | Bitcoin & Global Market Analysis |
| 06 | Deep Technical Analysis | Deep Technical Analysis |
| 07 | Spot Liquidity & Market Microstructure Analysis | Derivatives & Liquidity Analysis |
| 08 | On-Chain Intelligence Analysis | On-Chain Intelligence Analysis |
| 09 | Tokenomics & Fundamental Analysis | Tokenomics & Fundamental Analysis |
| 10 | Whale & Smart Money Tracking | Whale & Smart Money Tracking |
| 11 | Exchange Fund Flow Analysis | Exchange Fund Flow Analysis |
| 12 | Market Manipulation Detection | Market Manipulation Detection |
| 13 | Multi-Timeframe Confirmation | Multi-Timeframe Confirmation |
| 14 | Historical Performance Validation | Historical Performance Validation |
| 15 | AI Probability & Forecasting | AI Probability & Forecasting |
| 16 | Risk Management, Position Planning & Exact Trade Timing (Spot-specific rules) | Risk Management, Position Planning & Exact Trade Timing (Futures-specific rules) |
| 17 | Final Coin Selection & Ranking | Final Coin Selection & Ranking |
| 18 | Independent AI Red-Team Review | Independent AI Red-Team Review |
| 19 | Final Signal Audit & Entry Window Validation | Final Signal Audit & Entry Window Validation |
| 20 | Final Professional Report, Trade Timing & Decision | Final Professional Report, Trade Timing & Decision |

Phase 16 includes every subtask 16-1 through 16-9 in both prompts; the market-specific 16-8 rules must not be conflated.

### 2.6 Phase execution protocol and output continuity
Implement the full phase execution protocol from Part 5 of both prompts. Persist phase inputs, outputs, status, timestamps, provenance, missing-data records, decisions and continuation state. Support resumable execution without pretending an interrupted phase completed. Preserve required output delivery and continuity instructions.

### 2.7 Research quality and evidence requirements
Implement all Part 6 requirements from both prompts: source quality, evidence traceability, reproducibility, transparent calculations/methodologies, uncertainty, limitations, auditability and any prompt-specific research-quality constraints. Every material claim must be traceable to actual evidence or explicitly labeled as unavailable/inference.

### 2.8 Execution safety and trade-timing rules
Implement all Part 7 requirements from both prompts. The system is decision support, not an execution engine. Entry windows, dates, times, expirations, holding periods and conditional triggers must be evidence-based and bounded by freshness/signal validity. Never invent an entry time or imply a guaranteed future move. Maintain strict Spot-long-only and Futures contract-specific constraints.

### 2.9 Final system activation and operational modes
Implement all Part 8 requirements from both prompts, including:
- Pre-flight capability check for Binance live data, web/news access, code execution, on-chain provider access and reliable current time.
- Explicit consequences when a capability is unavailable.
- Re-validation mode for existing signals, including fresh data and the specified audit phases; do not reuse stale/expired signals.
- Full activation command and complete final report workflow.
- Quick-analysis mode must disclose that it is not a completed 20-phase analysis.

### 2.10 Final project closure (after both Phase 20 deliverables)
Do not declare the project complete merely because Phase 20 code exists. After SPOT Phase 20 and FUTURES Phase 20 both pass:
- Run full unit, integration, contract, regression and security tests.
- Verify all routes, services, persistence, scheduled/background work and MCP read-only interface.
- Verify live-data integrations and capability pre-flight in the intended deployment environment; record any external dependencies that cannot be validated.
- Verify every canonical prompt requirement has a traceable implementation/test/evidence reference or a formally documented limitation/blocker.
- Verify Spot/Futures separation, all no-fabrication rules, safety boundaries, timestamps, source provenance and resumability.
- Produce final acceptance matrix and operational runbook.
- Update readiness/status so no phase is marked complete without paired evidence.
- Document deployment/configuration, secrets setup, API limits, provider dependencies, monitoring, recovery, known limitations and safe usage.
- Only then mark overall project COMPLETE and create the final closure record/release.

## 3. Mandatory pre-coding audit of existing implementation

Before adding any new feature code in every coding session, audit the work already present in the repository. This applies at initial project start and every restart.

1. Map and inspect the existing architecture and code relevant to the project: providers, scanners, services, routes, schemas, configuration, persistence, background jobs, MCP interface, tests and security-sensitive components.
2. Compare the current implementation with both canonical prompts, this complete scope, the current phase checklist, API documentation/contracts and previously accepted evidence.
3. Run available existing tests and relevant lint, type, static analysis, import/build and security checks. Inspect actual failures and warnings; old CI success is not proof of current correctness.
4. Search for incorrect business logic/formulas/units, Spot-Futures mixing, incorrect API assumptions, incomplete market coverage, silent skips, missing failure ledgers, stale data represented as live, timestamp/timezone errors, unsafe defaults, credential leakage, race conditions, unhandled errors, contract mismatches and inadequate regression coverage.
5. Create an audit finding for each issue: severity, affected file/component and line where possible, reproducible evidence, impact, classification (confirmed defect or suspected risk), and recommended action.
6. Fix confirmed defects before new feature coding when they affect the current authorized phase, shared foundations, security, data integrity or already accepted functionality. Add regression tests where practical and rerun affected checks.
7. Do not use the audit to bypass phase locks. A defect exclusively belonging to a locked later-phase feature must be documented as DEFERRED / PHASE N LOCKED, not implemented early. Fix a later-area defect only when it is necessary to protect current-phase correctness, security or data integrity; explain the justification in the audit.
8. If a fix needs unavailable credentials, provider access, data or clarification, mark it BLOCKED with the exact resolution needed. Do not invent a workaround or change code speculatively.
9. New current-phase feature coding may begin only after the pre-coding audit is complete, confirmed in-scope defects are fixed or explicitly blocked, and regression checks are reviewed.

Every session's audit record must state inspected areas, commands/checks and actual results, confirmed defects, corrections, regression tests, suspected risks, deferred later-phase findings, blockers and whether the audit gate is COMPLETE or INCOMPLETE.

## 4. Mandatory phase gate — no exceptions

For each phase number N:
1. Read the canonical SPOT and FUTURES requirements for phase N.
2. Implement SPOT Phase N only; test and review against every SPOT task/output.
3. Implement FUTURES Phase N only; test and review against every FUTURES task/output.
4. Run paired regression/integration checks and inspect real response accounting where live access is available.
5. Record evidence, tests, data limitations, timestamps and review outcome.
6. Mark the combined phase COMPLETE and unlock N+1 only if both market-specific statuses are COMPLETE.
7. Otherwise retain IN_PROGRESS or BLOCKED and stop at N.

Statuses: NOT_STARTED, IN_PROGRESS, BLOCKED, COMPLETE.
Combined phase is COMPLETE if and only if both SPOT and FUTURES statuses are COMPLETE.
A passing test suite is necessary where tests apply, but not sufficient by itself.
No skipping, parallel phase advancement, inferred completion, phase merging or premature unlock.
Later-phase code may be inspected for dependencies, but must not be enhanced as later-phase implementation before its paired phase is authorized. Only changes strictly necessary for the current phase are allowed.
If blocked, record exact missing API/provider/credential/data/decision and the smallest required resolution. Do not silently bypass the blocker.

## 5. Paired phase ledger — source of truth for resume

| Phase | SPOT | FUTURES | Combined | Next phase |
|---|---|---|---|---|
| 01 | IN_PROGRESS | IN_PROGRESS | INCOMPLETE / ACTIVE | 02 LOCKED |
| 02 | NOT_STARTED | NOT_STARTED | LOCKED | 03 LOCKED |
| 03 | NOT_STARTED | NOT_STARTED | LOCKED | 04 LOCKED |
| 04 | NOT_STARTED | NOT_STARTED | LOCKED | 05 LOCKED |
| 05 | NOT_STARTED | NOT_STARTED | LOCKED | 06 LOCKED |
| 06 | NOT_STARTED | NOT_STARTED | LOCKED | 07 LOCKED |
| 07 | NOT_STARTED | NOT_STARTED | LOCKED | 08 LOCKED |
| 08 | NOT_STARTED | NOT_STARTED | LOCKED | 09 LOCKED |
| 09 | NOT_STARTED | NOT_STARTED | LOCKED | 10 LOCKED |
| 10 | NOT_STARTED | NOT_STARTED | LOCKED | 11 LOCKED |
| 11 | NOT_STARTED | NOT_STARTED | LOCKED | 12 LOCKED |
| 12 | NOT_STARTED | NOT_STARTED | LOCKED | 13 LOCKED |
| 13 | NOT_STARTED | NOT_STARTED | LOCKED | 14 LOCKED |
| 14 | NOT_STARTED | NOT_STARTED | LOCKED | 15 LOCKED |
| 15 | NOT_STARTED | NOT_STARTED | LOCKED | 16 LOCKED |
| 16 | NOT_STARTED | NOT_STARTED | LOCKED | 17 LOCKED |
| 17 | NOT_STARTED | NOT_STARTED | LOCKED | 18 LOCKED |
| 18 | NOT_STARTED | NOT_STARTED | LOCKED | 19 LOCKED |
| 19 | NOT_STARTED | NOT_STARTED | LOCKED | 20 LOCKED |
| 20 | NOT_STARTED | NOT_STARTED | LOCKED | FINAL CLOSURE LOCKED |

Ledger note: Phase 01 detailed outstanding criteria and evidence are maintained in docs/MASTER_PROMPT_IMPLEMENTATION_AUDIT.md. The audit and this ledger must be updated after every accepted work increment. Do not mark any checkbox complete without code/test/evidence references.

## 6. Phase completion evidence template

For each market-specific phase record:
- Canonical prompt file and exact phase heading/subheading.
- Requirement-by-requirement checklist.
- Code files/modules and API routes changed.
- Data providers/endpoints, official documentation reference and endpoint limitations.
- Tests added/changed and exact test command/result.
- Live or fixture response coverage: total, eligible, scanned, failed, excluded where applicable.
- Missing data and failure reasons; prove no silent skip.
- Source retrieval timestamps, freshness and timezone.
- Security/safety review.
- Known limitations and blocker owner/action.
- Reviewer decision: ACCEPTED or NOT ACCEPTED.
- Commit SHA and PR link.

## 7. Repository workflow and restart procedure
- Work on the existing audit branch / pull request unless the user explicitly directs otherwise.
- Keep canonical prompt files unchanged unless the user explicitly supplies a replacement.
- Keep this scope file, paired ledger and implementation audit synchronized.
- At the start of every resumed coding session, read both canonical prompts first, then this scope, then the implementation audit/ledger, then inspect current branch, commits, CI and working tree.
- Before any new feature coding, complete the mandatory audit in Section 3: inspect the code written so far, verify correctness against the specifications, fix confirmed in-scope errors, add regression tests and record deferred/blocked findings.
- Determine the earliest phase not COMPLETE in both markets. Resume that exact phase and market sequence; never trust conversational memory over repository state.
- Before editing, state the current phase, Spot/Futures statuses, exact next task and acceptance evidence.
- After editing, run appropriate tests, update ledger/audit, commit to the work branch and report verified links/results. Do not merge or modify main without explicit authorization.

## 8. Current restart checkpoint
- Current branch: work/dual-master-prompt-audit
- Current PR: https://github.com/mamunfb/universal-binance-ai-backend/pull/1 (draft)
- Current active phase: Phase 01 only.
- SPOT Phase 01: IN_PROGRESS.
- FUTURES Phase 01: IN_PROGRESS.
- Phase 02: LOCKED.
- The detailed Phase 01 remaining requirements are in docs/MASTER_PROMPT_IMPLEMENTATION_AUDIT.md.
- Phase 16 experimental code described in earlier audit history was reverted/deferred; do not reintroduce it before paired Phase 16 authorization.
- main branch has not been changed by this workstream.

## 9. Change log
- 1.0: Establish complete project scope from pre-phase configuration/global/API architecture through all 20 paired phases, post-phase protocols, research quality, execution safety, activation/revalidation and final closure. Establish restart contract and full paired ledger.
- 1.1: Add a mandatory pre-coding audit gate requiring review of existing implementation, correction of confirmed in-scope defects, regression testing, and explicit deferral of locked later-phase work.


## 10. Session audit checkpoint — 2026-11-11
- The session audit and verified correctness/security fixes are recorded in `docs/MASTER_PROMPT_IMPLEMENTATION_AUDIT.md`.
- Verified code-fix checkpoint: `721425b3b4f9eed02cf329d99b1a1bbca6e8e39d`; GitHub Actions passed with 525 tests and 2 warnings.
- SPOT Phase 01 and FUTURES Phase 01 remain IN_PROGRESS; Combined Phase 01 remains INCOMPLETE; Phase 02 remains LOCKED.
- The pre-coding full audit remains INCOMPLETE because not every existing service/module and local/deployment runtime state has been exhaustively verified. No new Phase 01 feature coding is authorized until that audit gate is completed.
- Local working-tree status is UNVERIFIED because the remote GitHub interface does not expose local uncommitted files.


## 11. Continued audit checkpoint — 2026-11-11
- Additional Spot scanner upstream-exception disclosure defect fixed and regression-tested; details and evidence are recorded in `docs/MASTER_PROMPT_IMPLEMENTATION_AUDIT.md`.
- Verified code/test checkpoint `898b21e731ad15e9636ae401bb652abf03a2ea8d`: GitHub Actions passed, including dashboard JavaScript syntax and 525 pytest tests (2 warnings).
- API/Futures/README documentation was corrected for default market coverage and COIN-M derived quote-notional units.
- Remaining audit items include provider rate-limit/retry policy, full per-symbol/per-contract failure reasons, all-eligible depth coverage, source-specific timestamps/freshness, review of all existing routes/services, static/security tooling and deployment/runtime verification.
- The MCP adapter contains a local SQLite snapshot-save POST tool; its compatibility with the literal final read-only MCP acceptance requirement needs an explicit architecture decision.
- Pre-Coding Full Audit remains INCOMPLETE. SPOT/FUTURES Phase 01 remain IN_PROGRESS; combined Phase 01 INCOMPLETE; Phase 02 LOCKED.


## 12. Security and static-analysis checkpoint — 2026-11-11
- Sanitized raw provider exception disclosure in Spot/Futures market-data API routes, cross-chain token intelligence and RSS feed failures; added regression tests.
- A broad Ruff check identified 289 existing diagnostics. CI now runs core Ruff correctness rules (`E4,E7,E9,F`) pending verification; full lint debt remains documented in the implementation audit.
- Latest combined test/lint CI verification is pending. Pre-Coding Full Audit remains INCOMPLETE; no Phase 01 feature implementation has started.


## 13. Verified security regression checkpoint — 2026-11-11
- Latest verified code/test checkpoint `dcfb8faf5372c0a9f75088d9e7f79afb9b2c42c7`: GitHub Actions SUCCESS; Ruff core checks, dashboard JavaScript syntax and pytest all passed; 528 tests passed with 2 warnings.
- A dedicated paired phase ledger is maintained at `docs/PAIRED_PHASE_LEDGER.md`.
- The broad repository Ruff scan reported 289 pre-existing diagnostics. CI currently checks core Ruff correctness rules on the reviewed security and Phase 01 files only; repository-wide lint cleanliness is not claimed.
- Pre-Coding Full Audit remains INCOMPLETE; SPOT/FUTURES Phase 01 remain IN_PROGRESS; Combined Phase 01 INCOMPLETE; Phase 02 LOCKED.


## 14. Session restart checkpoint — 2026-11-11 (repository and CI re-verification)
- Verified work branch: `work/dual-master-prompt-audit`; HEAD before this checkpoint: `21484ddb0bf4a4c7c6ec83279930546b4535405b`.
- PR #1 is OPEN / DRAFT / unmerged. Branch comparison at this checkpoint: 104 commits ahead of `main`, 0 behind. No merge or main-branch update was performed.
- Latest GitHub Actions run before this documentation checkpoint: `42933836840`, HEAD `21484ddb0bf4a4c7c6ec83279930546b4535405b`, conclusion SUCCESS. The actual job log reports Ruff core selection `E4,E7,E9,F` passed, dashboard JavaScript syntax passed, and pytest `554 passed, 2 warnings`.
- Current repository tree inventory: 80 FastAPI route decorators and 54 provider/service source files. Spot/Futures providers, Spot/Futures scanners, their scanner tests, CI workflow and the current phase ledger were directly inspected in this session.
- The mandatory pre-coding audit is still INCOMPLETE: the 80 routes and 54 provider/service files have not all received line-by-line acceptance review; deployment/live Binance connectivity, type checking, dedicated security scanning and local working-tree state remain unverified; provider retry/Retry-After policy and the MCP snapshot-save architecture decision remain open.
- Active phase remains paired Phase 01 only. SPOT Phase 01 and FUTURES Phase 01 remain IN_PROGRESS; Combined Phase 01 remains INCOMPLETE; Phase 02 remains LOCKED.
- No Phase 01 feature code was changed in this session because the scope's mandatory pre-coding audit gate has not yet been satisfied. No trading/order execution feature was added.


## 15. Provider rate-limit resilience correction — 4ecf7805578df40b6d80628144e100b454ace044
- Added `backend/app/providers/http_retry.py` as a market-neutral transport helper for idempotent public-data GET requests only.
- Integrated the helper into the separate Spot and USDⓈ-M / COIN-M Futures provider adapters without combining their endpoint paths or market calculations.
- HTTP 429 honors numeric or HTTP-date `Retry-After`; when absent/invalid it uses bounded exponential backoff. Transport errors and HTTP 5xx receive bounded retries. HTTP 418 (IP ban) is raised immediately and is not retried.
- Added retry regression tests for 429 header handling, 418 no-retry behavior, 503, transport failure, missing Retry-After fallback and HTTP-date parsing. Extended targeted Ruff CI coverage to the changed providers and new helper/tests.
- Commit: `4ecf7805578df40b6d80628144e100b454ace044`. GitHub Actions run `42957685379` was IN_PROGRESS when this checkpoint was written; do not treat tests as passed until its completed job log is reviewed.
- This is a correction to the documented API-reliability audit gap, not Phase 01 scanner feature acceptance. Spot/Futures Phase 01 remain IN_PROGRESS; Phase 02 remains LOCKED.
- No signed endpoints, order placement, cancellation, modification, withdrawal or wallet action was added.


## 16. Provider retry correction — verified CI checkpoint (2026-11-11)
- Code commit `4ecf7805578df40b6d80628144e100b454ace044`; GitHub Actions run `42957685379`: **SUCCESS**.
- Actual job log: targeted Ruff checks passed, dashboard JavaScript syntax passed, pytest **560 passed, 2 warnings**.
- This test count belongs to code commit `4ecf7805578df40b6d80628144e100b454ace044`. The current documentation HEAD `6d3db66cb0a00f9f0f1f83776d18536b335cc857` was committed after that run; do not attribute the exact 560 count to the docs-only HEAD without a separate run.
- Retry helper and both provider integrations are CI-verified. No live Binance 429/418 test has been performed.
- Phase 01 scanner requirements remain open; paired Phase 01 remains IN_PROGRESS / IN_PROGRESS / INCOMPLETE; Phase 02 LOCKED.


## 17. MCP integer-boundary hardening — 2026-11-11
- Current-session API inventory confirmed 80 FastAPI route decorators in `backend/app/main.py`; route surface is read-only with respect to Binance trading/order endpoints. The separate MCP adapter exposes 38 tools and includes one local research-snapshot persistence POST; it does not place, cancel, modify or sign exchange orders.
- Confirmed Python boundary hazard: `bool` is a subclass of `int`; several MCP integer parameters relied on range comparisons that accept `True` as integer 1. Added a reusable decorator that discovers declared integer/optional-integer annotations and rejects Boolean values before tool logic or API calls. Applied to all 38 registered MCP tools so new integer-annotated tools inherit the guard.
- Added parameterized regression tests covering Boolean values for a Spot kline limit, historical range timestamp, cross-chain decimals, aggregate-trade timestamp and research snapshot timestamp; tests assert no GET/POST request is issued.
- Code commit: `ae93896350a0cd4128a7a919bf32cace61582522`. GitHub Actions run `42958954122` was still IN_PROGRESS at this checkpoint; do not claim the new tests or lint passed until final run logs are reviewed.
- This is input-boundary hardening, not a Spot/Futures Phase 01 feature acceptance. SPOT Phase 01 and FUTURES Phase 01 remain IN_PROGRESS; combined Phase 01 INCOMPLETE; Phase 02 LOCKED.
- Full audit remains open: complete line-by-line review of all 54 provider/service modules and MCP snapshot persistence architecture decision are outstanding. Local working-tree state is not observable through the remote GitHub connector.


## 18. MCP integer-boundary CI verification — 2026-11-11
- Code commit `ae93896350a0cd4128a7a919bf32cace61582522`; GitHub Actions run `42958954122`: **SUCCESS**.
- Actual job log confirms targeted Ruff passed, dashboard JavaScript syntax passed, pytest **565 passed, 2 warnings**. The five new parameterized Boolean-as-integer cases passed.
- Current docs checkpoint commit follows the verified code/test commit; exact 565 count is attributed to `ae93896350a0cd4128a7a919bf32cace61582522`.


## 19. Scanner Boolean numeric-response validation — 2026-11-11
- Confirmed that both Phase 01 scanner helpers converted values with `float(value)` without rejecting Python Boolean values. Because `bool` is accepted by Python's numeric conversion, malformed Boolean ticker fields could become plausible numeric values.
- Both Spot and Futures scanner numeric parsers now reject Boolean values before conversion.
- Regression tests cover Spot lastPrice / priceChangePercent / quoteVolume; USDⓈ-M Futures equivalents; and COIN-M baseVolume fallback.
- Code/test commit: `d2a51830fc09ccbd819ecbf000415cd5c2d4b56d`. CI verification is pending; no test pass is claimed yet.
- This is a confirmed Phase 01 data-integrity bug fix. It does not complete the scanner's remaining coverage requirements or advance the paired phase gate.
- Pre-Coding Full Audit remains INCOMPLETE; SPOT Phase 01 and FUTURES Phase 01 remain IN_PROGRESS; Combined Phase 01 remains INCOMPLETE; Phase 02 remains LOCKED.


## 20. Stream numeric integrity and verified scanner correction — 2026-11-11
- Scanner Boolean numeric-response correction commit `d2a51830fc09ccbd819ecbf000415cd5c2d4b56d` passed GitHub Actions run `42959434159`: targeted Ruff passed, dashboard JavaScript syntax passed, pytest **567 passed, 2 warnings**. The exact count belongs to that code/test commit.
- Continued collector review found aggregate-trade normalization accepted Boolean/fractional values through `int()` and Boolean price/quantity values through `float()`; non-object JSON payloads could also raise before normalizer rejection. The normalizer now rejects non-object payloads, Boolean/fractional integer fields, negative IDs/timestamps, and Boolean price/quantity values.
- Added regression coverage for malformed trade IDs/timestamps, Boolean price/quantity, negative timestamps and non-object payloads.
- Aggregate-trade code/test commit: `e7c907e061828c92ec2536d1011cae252b74ff74`. Its CI verification is pending; no pass is claimed yet.
- These are data-integrity fixes only. The pre-coding audit and paired Phase 01 acceptance remain open; Phase 02 remains locked.


## 21. Stream and market-history numeric validation — 2026-11-11
- Aggregate-trade normalizer correction `e7c907e061828c92ec2536d1011cae252b74ff74` passed GitHub Actions run `42959561162`: targeted Ruff passed, dashboard JavaScript syntax passed, pytest **568 passed, 2 warnings**. This exact count belongs to that commit.
- Further audit found Boolean numeric coercion and permissive `int()` truncation at funding-rate, open-interest and historical-kline persistence boundaries, plus Boolean numeric/timestamp acceptance in liquidation normalization.
- Funding and OI stores now require integer (non-Boolean) timestamps and reject Boolean float-like metric fields. Historical klines require integer (non-Boolean) open/close timestamps and trade counts and reject Boolean OHLCV fields. Liquidation normalization rejects non-object payloads, Boolean numeric values and non-integer/Boolean timestamps.
- Code/test commit: `4c9b1604f170ea1c5d5eaa097136f93851518117`. CI verification pending.
- These corrections harden ingestion integrity only. They do not satisfy Phase 01 scanner coverage or change paired phase statuses.


## 22. Derivatives storage timestamp validation — 2026-11-11
- Funding-rate, open-interest, historical-kline and liquidation input hardening commit `4c9b1604f170ea1c5d5eaa097136f93851518117` passed CI run `42959727771`: Ruff passed, dashboard JavaScript syntax passed, pytest **586 passed, 2 warnings**.
- Continued review found the derivatives ratio store accepted Boolean/fractional timestamps via `int()`, while derivatives signal snapshots accepted Boolean end timestamps because `bool` is an `int` subclass. These boundaries now require non-Boolean integer timestamps; snapshot history also validates integer limit/time bounds.
- Code/test commit: `2b0b8d33cbcf5b1a9a13be97808aa76e21b4b63d`. CI verification pending.
- Paired Phase 01 statuses remain unchanged; Phase 02 remains locked.


## 23. Derivatives timestamp hardening — verified CI checkpoint (2026-11-11)
- Code/test commit `2b0b8d33cbcf5b1a9a13be97808aa76e21b4b63d`; GitHub Actions run `42959858424`: **SUCCESS**. Actual job log confirms Ruff passed, dashboard JavaScript syntax passed, pytest **591 passed, 2 warnings**.
- This verifies rejection of Boolean/fractional derivatives-ratio timestamps and Boolean/fractional/negative derivatives-snapshot end timestamps, plus history-bound validation.
- The current documentation HEAD before this checkpoint is `6a384ce460d5f524136fc43df389d2c360356fba`; its own CI run must be checked separately. Do not transfer the 591-pass count to documentation-only commits.
- The pre-coding audit and paired Phase 01 gates remain open; Phase 02 remains locked.


## 24. Order-flow and data-quality request validation — 2026-11-11
- Order-flow numeric-boundary correction commit `40e37bb1a758cad86564310b46989f0f88de0881` passed GitHub Actions run `42960326700`: targeted Ruff passed, dashboard JavaScript syntax passed, pytest **592 passed, 2 warnings**.
- The order-flow analyzer now rejects Boolean/fractional request timestamps, Boolean thresholds, malformed non-object trade rows, Boolean/fractional trade timestamps and Boolean price/quantity/notional fields rather than coercing them.
- Historical coverage request bounds now require non-Boolean integers and its expected-candle safety limit must be a positive integer. Market data quality lookback and optional now_ms controls now reject Boolean/fractional/negative values.
- Code/test commit for these latest coverage/data-quality changes: `feccc885dde07c86eb0c531b30507dbeafadf2d9`. CI status must be checked; no test pass is claimed yet.
- No phase status changes. Paired Phase 01 remains INCOMPLETE and Phase 02 LOCKED.


## 25. Liquidity-analysis input validation — 2026-11-11
- Historical coverage / market-data-quality request validation commit `feccc885dde07c86eb0c531b30507dbeafadf2d9` passed GitHub Actions run `42960402710`: targeted Ruff passed, dashboard JavaScript syntax passed, pytest **598 passed, 2 warnings**.
- Liquidity behavior parser now rejects Boolean/fractional/negative timestamps and Boolean/non-finite numeric metrics, counts rejected snapshots/trades, and validates depth rows without coercing Boolean values.
- Liquidity sweep confirmation now rejects Boolean/fractional candle timestamps, duplicate candle opens, Boolean OHLC, malformed trade timestamps, and invalid numeric/time-window controls; nearest timestamp joins no longer truncate malformed values.
- Liquidity behavior code/test commit `923369a5b2bb9a17a0a887b17f175e22788fb65a` passed CI run `42960545107`: targeted Ruff passed, dashboard JS passed, pytest **600 passed, 2 warnings**.
- Liquidity sweep code/test commit `f43f4a6f81aa2cf2100c83f681d6d4bf8b851e9c` is queued/in progress at this checkpoint; do not claim verified until its job log is inspected.
- Paired Phase 01 statuses remain unchanged; Phase 02 remains LOCKED.


## 26. Liquidity sweep and performance request-boundary verification — 2026-11-11
- Liquidity sweep validation commit `f43f4a6f81aa2cf2100c83f681d6d4bf8b851e9c` passed Actions run `42960668769`: targeted Ruff passed, dashboard JavaScript syntax passed, pytest **602 passed, 2 warnings**.
- Market confluence performance evaluator now rejects Boolean/fractional `limit` and `hours` request arguments instead of allowing Boolean-as-int or non-integer bounds. Regression tests cover evaluate and price_path.
- Performance argument validation code/test commit: `78b9831806e7dd084b226e5b7826e2b67919f371`; CI pending.
- No phase acceptance status changes.


## 27. Performance evaluator argument validation — verified (2026-11-11)
- Code/test commit `78b9831806e7dd084b226e5b7826e2b67919f371`; Actions run `42960815725`: **SUCCESS**. Actual job log confirms Ruff passed, dashboard JavaScript syntax passed, pytest **603 passed, 2 warnings**.
- Strict non-Boolean integer validation for performance evaluator `limit` and `hours` is verified. This is request-boundary hardening only; no paired phase acceptance criteria are closed by this fix.


## 28. Liquidation cluster query-bound validation — 2026-11-11
- Liquidation cluster analysis now rejects Boolean/fractional time bounds, Boolean/fractional limit values, and non-integer bucket/minimum-event controls instead of accepting Boolean-as-int or implicit numeric comparison.
- Added regression tests for each request-bound category.
- Code/test commit: `f3bc28e1b37a896ddd4034440523f897b4d45c27`; CI status must be verified before marking this change accepted.
- The preceding performance evaluator code/test commit `78b9831806e7dd084b226e5b7826e2b67919f371` passed run `42960815725`: Ruff and dashboard JS passed, pytest **603 passed, 2 warnings**.
- Paired phase statuses remain unchanged.
