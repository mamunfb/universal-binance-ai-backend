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
