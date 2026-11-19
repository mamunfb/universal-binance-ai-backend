# GOVERNANCE PRECEDENCE — CURRENT POLICY (2026-11-19)

> **This notice supersedes every conflicting software-development phase gate, paired-phase lock, per-session full-audit mandate, and “Phase N+1 LOCKED” instruction appearing later in this historical scope document.** Those instructions are retained below as historical project context only. They are not active engineering controls. The active engineering rules are in [PROJECT_EXECUTION_GOVERNANCE.md](PROJECT_EXECUTION_GOVERNANCE.md), and current package status is in [PROJECT_PROGRESS_LEDGER.md](PROJECT_PROGRESS_LEDGER.md). Session startup is controlled by [MASTER_RESUME_PROMPT.md](../master-prompts/MASTER_RESUME_PROMPT.md).

## Two separate kinds of sequencing — do not conflate them

1. **Software engineering:** use one active task/work package at a time, selected by dependency and priority. There is no paired SPOT/FUTURES phase lock, no automatic “next phase” lock, and no requirement to finish all SPOT engineering for a numbered phase before FUTURES engineering. A package is accepted only with its applicable implementation, verification and evidence. Reopen only the affected package and materially dependent packages when a confirmed regression requires it.
2. **Crypto market analysis:** the 20-phase analytical workflow defined inside each canonical SPOT and FUTURES master prompt remains part of that prompt's functional requirements. Preserve its internal phase order, market-specific rules, outputs, safety checks and evidence requirements during an analysis. This analytical sequence does not impose a software-development task lock or require SPOT and FUTURES engineering to advance as a pair.

## Active source-of-truth order

For engineering workflow and progress, follow this order: (1) latest explicit user instruction; (2) `docs/PROJECT_EXECUTION_GOVERNANCE.md`; (3) `docs/PROJECT_PROGRESS_LEDGER.md`; (4) `master-prompts/MASTER_RESUME_PROMPT.md`; (5) this document's still-applicable project scope and safety requirements. Historical audit entries and old paired-ledger content are evidence of past decisions, not active workflow commands. For crypto-analysis behavior, the two canonical market prompts remain authoritative within their respective markets.

---

# UNIVERSAL BINANCE AI BACKEND — COMPLETE PROJECT SCOPE & EXECUTION CONTROL

Version: 2.0
Status: ACTIVE — functional scope remains authoritative; software task sequencing is governed by PROJECT_EXECUTION_GOVERNANCE.md.
Repository: mamunfb/universal-binance-ai-backend
Canonical specifications:
- master-prompts/MASTER_PROMPT_01_SPOT.md (Master Prompt 01 — SPOT)
- master-prompts/MASTER_PROMPT_02_FUTURES.md (Master Prompt 02 — FUTURES)

## 1. Authority and precedence

This document defines the repository-wide product scope, functional requirements, safety constraints and market-analysis deliverables. It does not impose software-development phase locks or a fixed engineering task order. Software task sequencing, package acceptance and restart behavior are governed by docs/PROJECT_EXECUTION_GOVERNANCE.md and docs/PROJECT_PROGRESS_LEDGER.md. The two canonical master prompts remain the detailed functional specifications; this document or a future implementation must not shorten, replace, reinterpret or silently override their market-specific requirements.

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

### 2.5 Complete 20-phase analysis workflows — separate market specifications
Each canonical prompt defines its own 20-step analytical workflow. Preserve the exact task lists, subheadings, order and outputs in the relevant prompt. SPOT and FUTURES analysis results must remain distinct and must not be blended. The table below is a cross-market scope map only; it does not require engineering implementation to advance in paired numbered phases, and it does not create a Phase N+1 software lock.

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

### 2.10 Final project closure
Do not declare the overall product complete merely because implementation code exists or an isolated analysis phase passes. Before overall closure, verify that the applicable Spot and Futures capabilities and their final analytical workflows meet their own acceptance criteria:
- Run full unit, integration, contract, regression and security tests.
- Verify all routes, services, persistence, scheduled/background work and MCP read-only interface.
- Verify live-data integrations and capability pre-flight in the intended deployment environment; record any external dependencies that cannot be validated.
- Verify every canonical prompt requirement has a traceable implementation/test/evidence reference or a formally documented limitation/blocker.
- Verify Spot/Futures separation, all no-fabrication rules, safety boundaries, timestamps, source provenance and resumability.
- Produce final acceptance matrix and operational runbook.
- Update readiness/status so no phase is marked complete without paired evidence.
- Document deployment/configuration, secrets setup, API limits, provider dependencies, monitoring, recovery, known limitations and safe usage.
- Only then mark overall project COMPLETE and create the final closure record/release.

## 3. Risk-based review and verification for each work package

Use the change-focused review process in docs/PROJECT_EXECUTION_GOVERNANCE.md. Before editing a package:
1. Inspect the code, interfaces, dependencies, tests and documentation materially related to that package.
2. Reconcile relevant historical findings and acceptance evidence with the current branch and current implementation.
3. Run targeted tests and checks appropriate to the changed behavior and risk surface.
4. Expand the review when the change crosses boundaries, touches security/data integrity, affects Spot/Futures separation, or reveals a systemic defect.
5. Record confirmed defects, suspected risks, severity, reproducible evidence, impact and resolution.
6. Fix confirmed defects that affect the active package or create material security/data-integrity risk; add regression tests where practical.
7. Record genuine blockers with the exact missing input/access and smallest resolution. Do not invent workarounds or change code speculatively.

A full-codebase audit and full-suite run are not mandatory at every session. Use a risk-based review and retain exact test/CI evidence tied to the relevant commit.

## 4. Engineering task governance — no paired phase lock

Software engineering is organized as dependency-aware work packages with one active package at a time. There is no requirement to complete SPOT Phase N engineering and FUTURES Phase N engineering as a pair, and no Phase N+1 lock. A task may proceed when its actual prerequisites are met.

Use the active statuses and completion rules in docs/PROJECT_EXECUTION_GOVERNANCE.md. A package is COMPLETED only when its applicable implementation, tests, review and evidence are recorded. A passing test suite alone is not sufficient. If a task is blocked, record the concrete blocker; unrelated tasks are not automatically locked.

The 20 analytical phases inside each canonical prompt remain sequential within that market-analysis workflow. This analytical order does not control the order of software implementation packages.

## 5. Engineering progress ledger

The active engineering source of truth is docs/PROJECT_PROGRESS_LEDGER.md. It tracks work packages and their evidence. Do not use the former paired SPOT/FUTURES ledger or old Phase 01/Phase 02 statuses to infer current package status. Unknown package states remain UNASSESSED until reconciled against repository evidence.

The former paired ledger is retained only as a retirement pointer at docs/PAIRED_PHASE_LEDGER.md. Historical implementation findings remain in docs/MASTER_PROMPT_IMPLEMENTATION_AUDIT.md and must not be mistaken for current task status.

## 6. Market-analysis deliverable evidence template

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

Follow docs/PROJECT_EXECUTION_GOVERNANCE.md and master-prompts/MASTER_RESUME_PROMPT.md:
- Read the active governance and progress ledger first.
- Read the relevant canonical market prompt sections for the package being resumed; read both prompts fully when establishing or materially revising their implementation contract.
- Inspect the current branch, HEAD, PR, relevant CI jobs, changed files and tests.
- Continue one active work package at a time, based on user priority, dependencies and evidence.
- Use targeted review and verification; do not repeat a full-codebase audit at every session by default.
- Update the task ledger and relevant audit evidence after meaningful work.
- Do not infer package completion from historical phase statuses or old chat messages.
- Do not modify main, merge a PR, deploy to production or alter production databases/secrets without explicit user authorization.

## 8. Historical restart checkpoint — 2026-11-11 (not current state)
The following records describe the former paired-phase workflow and are preserved for historical traceability only. They are not the current restart point and must not be used to assign current work-package statuses.
- Historical branch: work/dual-master-prompt-audit
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
- 1.1: Add the former paired-phase pre-coding audit gate (retired on 2026-11-19).
- 2.0: Separate the canonical 20-step market-analysis workflows from engineering task governance; retire paired development-phase locks and replace the active engineering ledger with evidence-based work packages.


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


## Latest provider audit checkpoint — RSS feed boundaries (2026-11-11)

The RSS provider now disables redirects and enforces a configurable streamed response-size ceiling (1 MiB by default). Regression tests cover redirect rejection, oversized feed rejection, and invalid limits. Implementation commit `046bba3b253a99b70076a68344fe8d3a468291f6`; test commit `cf36eb8a1608bca207c9882ae0778a8560b951b3`. CI run `42962156783` must be checked before treating this change as verified. This does not close the pre-coding audit or advance Phase 01 acceptance.


### RSS feed correction — CI verified

- Code/test commit `cf36eb8a1608bca207c9882ae0778a8560b951b3`; GitHub Actions run `42962156783`: **SUCCESS**.
- Actual job log confirms targeted Ruff passed, dashboard JavaScript syntax passed, and pytest **607 passed, 2 warnings**.
- The two pytest warnings are existing Starlette/httpx TestClient and FastAPI parameter deprecations. The workflow also emits a Node.js 20 deprecation notice during cleanup.
- This CI run verifies the RSS redirect/size-limit change and regression tests at the code/test commit. Later documentation-only commits have their own CI runs and must be checked independently.
- Paired Phase 01 remains IN_PROGRESS for Spot and Futures; combined Phase 01 remains INCOMPLETE; Phase 02 remains LOCKED. Full pre-coding audit remains open.


## EVM RPC response-boundary hardening — 2026-11-11

- EVM RPC endpoint validation now parses the URL and rejects malformed HTTPS URLs, missing hosts, embedded credentials, fragments, whitespace, and invalid ports.
- JSON-RPC POST requests explicitly disable redirects even when a caller supplies an AsyncClient configured to follow redirects.
- Response bodies are consumed incrementally with a configurable 2 MiB default byte ceiling; oversized responses fail before JSON parsing. Invalid size-limit configuration is rejected.
- Regression tests cover malformed/credentialed endpoint URLs, redirect refusal with a redirect-enabled client, oversized streamed responses, and invalid size-limit values.
- Implementation commit: `5cebc659b692d5cff5c35a698a938606b41ba7d1`; tests commit: `febed5f5af364219bac9e7496bb2f28e2f03bfa7`.
- GitHub Actions run `42967238068` on the test commit: **SUCCESS**; targeted Ruff passed, dashboard JavaScript syntax passed, and pytest **619 passed, 2 warnings**.
- The EVM RPC hardening is a provider-level boundary correction only. EVM transfer-index store/API audit and full route security review remain open. This does not complete the full project audit or change paired phase acceptance.
- SPOT Phase 01: IN_PROGRESS; FUTURES Phase 01: IN_PROGRESS; Combined Phase 01: INCOMPLETE; Phase 02: LOCKED. No order execution or wallet signing capability was added.


## EVM historical-flow coverage status correction — 2026-11-11

- Route audit found `GET /api/v1/onchain/evm/token/{contract}/history/flows` always returned `status=COMPLETED` even when the local SQLite index contained gaps in the requested block interval. The response exposed raw indexed ranges but did not calculate coverage for the requested interval.
- The route now computes `range_coverage(chain_id, contract, from_block, to_block)`, returns that structured coverage object, and reports `INCOMPLETE` whenever gaps remain. `COMPLETED` is returned only when the full requested interval is covered.
- Route regression tests cover both incomplete and complete indexed intervals.
- Implementation commit `b5ff75782f87c0b526bb5b126a64d3492c44d950`; test commit `6549471718ef4c90b9047f0d52378b3705173673`.
- GitHub Actions run `42967489250` on the test commit: **SUCCESS**; targeted Ruff passed, dashboard JavaScript syntax passed, and pytest **621 passed, 2 warnings**. Implementation-only run `42967453504` also passed with 619 tests.
- Remaining EVM route/store audit is still open; this correction does not complete the route security review or the overall audit. Paired Phase 01 remains INCOMPLETE; Phase 02 remains LOCKED.


## EVM transfer index validation checkpoint — 2026-11-11

- `EVMTransferStore.save_chunk` now validates chain ID and requested block range, requires a list of logs, accepts only the ERC-20 Transfer event signature, validates transaction/block/log/data hex fields and 32-byte transfer data, validates indexed address topic padding, rejects malformed `removed` flags, and checks any returned log contract address against the requested contract.
- Store query methods now validate chain/contract/block scopes and strict non-Boolean integer controls for limits, decimals, and window sizes.
- The historical indexer now validates block bounds, chunk size and total-block limit before RPC calls, and rejects invalid provider chain IDs/latest block numbers.
- Regression tests cover wrong event signatures, contract mismatch, malformed removed flags, invalid scope values, and Boolean integer controls.
- Code commits: `1acf62a6af082fc908c6c3599b857faecd824e24`, `054c4c2af077905debee1e16c5e326c78ce6dabd`, `73e225579162c845b8fd039d377633a63b71c146`.
- Test commits: `9d51a666dce0879456a2e0a33736b4663ce8842f`, `c6578e3af919577c13e8dd5354303d4665b38e12`, `16eb50261625fac8837060763c8403ebb84b17eb`, `f5ad937d353bd6f5e2f372949934d57db68dff5f`, `ef80f5c372dbc8f0a0ba01133a7911a0ddc1d626`.
- Latest combined GitHub Actions run `42967937288`: **SUCCESS**; Ruff passed, dashboard JavaScript syntax passed, pytest **634 passed, 2 warnings**.
- The tests enforce canonical 32-byte ABI event data; early test-fixture runs exposed shorter noncanonical sample data and those fixtures were corrected before the final successful run.
- Full EVM indexing/reorg/route audit remains open. This checkpoint does not constitute full project audit completion or phase acceptance. SPOT and FUTURES Phase 01 remain IN_PROGRESS; combined Phase 01 remains INCOMPLETE; Phase 02 remains LOCKED.


## EVM transfer re-indexing and history coverage checkpoint — 2026-11-11

- Duplicate `transactionHash/logIndex` identities within a single RPC chunk are now rejected before any database write; this prevents conflicting duplicate payload entries from silently overwriting one another while inflating the chunk transfer count.
- Added regression coverage for atomic rejection of duplicate log identities and for `removed=true` tombstones: removed logs are excluded from history, and a subsequent canonical replay can restore the same identity as active.
- The read-only `GET /api/v1/onchain/evm/token/{contract}/history` route previously returned `COMPLETED` regardless of gaps. It now calculates requested-range coverage and reports `INCOMPLETE` unless the entire requested interval is covered. API tests cover complete and incomplete ranges.
- Duplicate/reorg-behavior code commit: `a1dcba2d905df322f8f72d60431d3b2ebde2ad78`; test commit: `0070c1faaf123e99eca321fe4591e6a047d0829c`.
- History coverage route commit: `a39703b46c25a629f898d9c007071b6a55936aee`; API test commit: `89b96fe52e18a345e8c24f283baece7b9aea12b2`.
- Duplicate/replay regression CI run `42968331186`: **SUCCESS**, Ruff and dashboard JavaScript syntax passed, pytest **636 passed, 2 warnings**. History route implementation CI run `42968449219`: **SUCCESS**, pytest **636 passed, 2 warnings**. The final API-test commit CI is still running at this checkpoint; do not treat its result as verified until the run completes.
- Reorganization support is only partially addressed: the store honors explicit `removed=true` log tombstones and permits replay, but does not yet persist per-block hashes or independently detect/reconcile a provider's changed canonical chain. That remains an open audit item.
- Overall EVM store/API audit remains open. No phase acceptance is claimed. SPOT and FUTURES Phase 01 remain IN_PROGRESS; combined Phase 01 remains INCOMPLETE; Phase 02 remains LOCKED.


## CI result correction — EVM history API tests — 2026-11-11

- Final API-test commit `89b96fe52e18a345e8c24f283baece7b9aea12b2`, GitHub Actions run `42968465052`: **SUCCESS**; Ruff passed, dashboard JavaScript syntax passed, pytest **638 passed, 2 warnings**. This supersedes the earlier interim note that recorded the run as pending and the prior test count of 636.
- Documentation checkpoint commits `9a324a880160cf9d7cb614945149e343d8c56904`, `54656c9af01b93a1e4a0c7621605488030844aa6`, and `aa1e2b610c4957929ce281d12f3149ae9681f3c5` also passed CI in runs `42968572627`, `42968575864`, and `42968587052`, respectively.



## EVM wallet registry input-validation checkpoint — 2026-11-11

- Route/service audit found malformed wallet registry fields could raise uncaught type errors rather than a controlled validation failure: for example, list/dict labels or statuses, non-string evidence URLs, malformed URL ports, and invalid address values passed to the annotation helper.
- Registry loading now validates non-Boolean non-negative chain IDs, strict 20-byte hexadecimal EVM addresses, allowed input fields, string types and bounded lengths for metadata/evidence, and HTTPS evidence URLs with a host and no embedded credentials. Label and verification-status types are checked before set membership.
- Wallet annotation now validates the input collection, registry wallet-list shape, and every address before normalization.
- Code commits: `c541cda69dbc4f87eb8a006ae3851316457dd80b` and `3d5e9bafef6a22d9ef9f2e26e1dbec69143a2f45`; regression-test commit: `0cfde9fbd0d049976e7f669fad5d96cfd6e975bc`.
- Added tests for malformed field types, unknown keys, credentialed/malformed HTTPS URLs, invalid chain IDs, invalid address inputs, and malformed annotation containers. CI result is pending and must be verified before this checkpoint is marked green.
- This is a focused registry validation correction, not completion of the EVM API/store audit. Reorg canonical-chain reconciliation, route-level review, SQLite concurrency behavior, and full JSON-RPC response validation remain open.
- SPOT Phase 01: IN_PROGRESS; FUTURES Phase 01: IN_PROGRESS; Combined Phase 01: INCOMPLETE; Phase 02: LOCKED. No execution or wallet-signing capability was added.



## CI verification — EVM wallet registry validation — 2026-11-11

- Final validation code/test state was exercised by GitHub Actions run `42969334742`: **SUCCESS**, Ruff passed, dashboard JavaScript syntax passed, pytest **657 passed, 2 warnings**.
- The workflow initially did not include the new wallet-registry service and test files in its explicit Ruff target list. The workflow was corrected in commit `5a90d60aba576c9c9b06df42dcb0904d6fb245cf` to lint both files.
- Final workflow run `42969542488` on that workflow commit: **SUCCESS**; its actual job log confirms Ruff included `backend/app/services/wallet_attribution.py` and `tests/test_wallet_attribution.py`, all checks passed, dashboard JavaScript syntax passed, and pytest **657 passed, 2 warnings**.
- Documentation checkpoint runs `42969353873`, `42969372772`, and `42969405615` also completed successfully.
- This verifies the wallet-registry validation change and lint coverage, not the full EVM route/store audit. Canonical reorg reconciliation, full API route review, SQLite concurrency/atomicity under concurrent writers, and broader RPC protocol validation remain open.
- SPOT Phase 01: IN_PROGRESS; FUTURES Phase 01: IN_PROGRESS; Combined Phase 01: INCOMPLETE; Phase 02: LOCKED. No execution or wallet-signing capability was added.



## EVM transfer-index API request schema checkpoint — 2026-11-11

- The read-only indexing endpoint accepted a generic JSON object and silently ignored unrecognized keys. This could hide client-side field-name mistakes while returning a successful indexing result.
- `POST /api/v1/onchain/evm/token/{contract}/index` now rejects unknown body fields and non-object payloads before starting provider work. Required fields, Boolean-vs-integer checks, block-range checks, and chunk-size limits remain enforced.
- Added API-level regression tests for unknown/misspelled fields, Boolean block values, and missing required fields; each confirms HTTP 422 and no RPC attempt.
- Implementation commit: `0de572963738cb5a32d9ae2386425ff0039f6710`; test commit: `4934ec8aa150f6233b2ea0f120cf1180ba091ecf`; Ruff workflow scope commit: `2fb64e016d6c8012c16120c507d6de5ff4b9159b`.
- CI verification is pending for the latest combined state; do not mark this checkpoint green until the workflow job log confirms Ruff, dashboard syntax, and pytest.
- This remains a focused route input-schema correction. It does not complete EVM JSON-RPC response validation, canonical reorg reconciliation, SQLite concurrency review, or the complete route audit.
- SPOT Phase 01: IN_PROGRESS; FUTURES Phase 01: IN_PROGRESS; Combined Phase 01: INCOMPLETE; Phase 02: LOCKED. No order execution or wallet-signing capability was added.



## CI verification — EVM transfer-index request schema — 2026-11-11

- Implementation commit `0de572963738cb5a32d9ae2386425ff0039f6710`, API regression-test commit `4934ec8aa150f6233b2ea0f120cf1180ba091ecf`, and Ruff-scope commit `2fb64e016d6c8012c16120c507d6de5ff4b9159b`.
- GitHub Actions run `42969759999`: **SUCCESS**; actual job log confirms Ruff passed with the new API test included, dashboard JavaScript syntax passed, and pytest **661 passed, 2 warnings**.
- Documentation checkpoint run `42969784105` also completed successfully with the same 661-test suite. The remaining documentation commit's run is tracked separately.
- Unknown/misspelled body fields, Boolean block numbers, and missing required keys are rejected as HTTP 422 before provider calls. This closes only the identified request-schema gap; the full API audit remains open.



## EVM JSON-RPC response-envelope hardening checkpoint — 2026-11-11

- Protocol review found the response ID comparison used Python equality, under which Boolean `true` compares equal to integer request ID `1`. The response parser also did not enforce the JSON-RPC requirement to return exactly one of `result` or `error`, or validate the error object shape.
- The provider now requires an integer (not Boolean) matching response ID, exactly one result/error member, and an error object with a non-Boolean integer code and non-empty message. Error text from the provider is not echoed in the raised exception.
- Added regression cases for Boolean IDs, absent/both result and error members, malformed error objects, and safe handling of provider error messages.
- Provider commit: `3814d73fc08906697245f68593c29efcc93335c9`; test commit: `9bac11a10dd2a00f68180a77163d822d9d007a7e`; Ruff-scope commit: `af744441febcff9bec614ca1623b7d93924ffab6`.
- CI is pending for this checkpoint. No success is claimed until the complete job log verifies Ruff, JavaScript syntax, and pytest.
- This is a protocol-envelope correction only; chain-specific result schemas, provider canonical-chain behavior, reorg handling, and the full route/provider audit remain open.
- SPOT Phase 01: IN_PROGRESS; FUTURES Phase 01: IN_PROGRESS; Combined Phase 01: INCOMPLETE; Phase 02: LOCKED. No order execution or wallet-signing capability was added.



## CI verification — strict EVM JSON-RPC response envelope — 2026-11-11

- The first provider-only CI run `42969960107` correctly exposed an outdated test expectation for a missing result field; the implementation behavior was intentional, and the regression expectation was updated to the stricter exactly-one-of-result/error rule.
- Final test commit `9bac11a10dd2a00f68180a77163d822d9d007a7e` passed run `42969997843`.
- Final workflow commit `af744441febcff9bec614ca1623b7d93924ffab6` passed run `42970015889`; the Ruff command explicitly included `backend/app/providers/evm_rpc.py` and `tests/test_evm_rpc_provider.py`. The complete job passed Ruff, dashboard JavaScript syntax, and pytest **666 passed, 2 warnings**.
- This verifies the response-envelope change and its test/lint coverage. It does not verify every chain-specific RPC result shape or production RPC behavior.



## CI test-count correction — 2026-11-11

- Correction to the immediately preceding JSON-RPC CI note: run `42970015889` completed with pytest **665 passed, 2 warnings**, not 666. The run log explicitly reports `665 passed, 2 warnings in 6.13s`.
- Ruff passed with the EVM RPC provider and its tests in the lint target; dashboard JavaScript syntax also passed. The verified test count is 665.


## EVM canonical block-checkpoint and fork invalidation checkpoint — 2026-11-11

- Added read-only eth_getBlockByNumber header retrieval with strict requested-height, 32-byte hash, and parent-hash validation.
- SQLite now persists chain-level block-hash/parent-hash checkpoints. The indexer records chunk boundary checkpoints and refreshes the nearest stored checkpoint before and after an overlapping requested subrange.
- When a stored checkpoint hash or adjacent parent linkage changes, the store conservatively invalidates transfer rows from the earliest possible fork point, deletes every overlapping coverage range for that chain (including other token contracts), and then writes the newly indexed chunk and refreshed checkpoints in the same SQLite transaction.
- When a chain has legacy indexed coverage but no canonical hash checkpoints, the first checkpointed index invalidates those unhashed rows/ranges rather than presenting unverifiable legacy history as canonical.
- Regression tests cover block-header RPC validation, changed chunk-end hashes, fork detection while reindexing partial subranges using bracketing checkpoints, conservative coverage-gap reporting, and legacy unhashed-coverage migration.
- Implementation commits include 531abb913d0aab0e92d072933e5613779c285647, cdc011b6db9463dbe95276500ff32e67b11428dd, 619a469113124cbb5b5b438453e83a437790ed86, 7371160cbff12ac0ac8bf4b7b106dadcfd8708c6, cad44725559d2105e7906ffd89ca43a7085ff323, aa4b8e39a7431e85b1ad2fab356438cefd8bf345, and e8664a857f32a8ea18aa3f6abbdf5513724b4641.
- Latest canonical checkpoint regression workflow is pending; no green status is claimed until the full job finishes.
- This is reorg detection on subsequent indexing/reindexing, not a background watcher. A chain that is never re-indexed after a reorg is not automatically reconciled. SQLite concurrent-writer stress and complete route audit remain open.
- SPOT Phase 01: IN_PROGRESS; FUTURES Phase 01: IN_PROGRESS; Combined Phase 01: INCOMPLETE; Phase 02: LOCKED. No order execution or wallet-signing capability was added.
