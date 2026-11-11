# Master Prompt 01 (SPOT) + Master Prompt 02 (FUTURES) — Repository Gap Audit

Audit basis:
- Repository: \`mamunfb/universal-binance-ai-backend\`
- Baseline branch: \`main\`, commit \`dfef59340c08fd20ba858efb78016ff8ff4e3997\`
- Spot prompt: \`master-prompts/MASTER_PROMPT_01_SPOT.md\`
- Futures prompt: canonical user-uploaded \`universal_crypto_master_prompt_futures.md\`, copied verbatim to \`master-prompts/MASTER_PROMPT_02_FUTURES.md\` on this branch
- Review method: static review of repository tree, README, API routes, providers, analysis services, readiness map, and selected tests. This document is not a claim that all tests or live endpoints were executed.

## Repository control documents

- Complete end-to-end scope and paired execution ledger: `docs/UNIVERSAL_PROJECT_SCOPE_AND_EXECUTION_CONTROL.md`.
- Session restart/controller prompt: `master-prompts/MASTER_RESUME_PROMPT.md`.
- Canonical functional specifications: `master-prompts/MASTER_PROMPT_01_SPOT.md` and `master-prompts/MASTER_PROMPT_02_FUTURES.md`.
- At the start of every resumed coding session, read both canonical prompts first, then the scope, then this audit, and reconcile GitHub/CI before editing.

The scope also mandates a pre-coding audit of all existing implementation at every session restart: inspect code and contracts, run available checks, identify confirmed defects, fix in-scope defects with regression tests before new feature coding, and defer work belonging only to locked later phases. See Section 3 of the scope and the mandatory audit section in the Resume Prompt.

The scope covers the work before Phase 01 (configuration, global rules, API architecture), all 20 paired phases, and work after Phase 20 (phase protocol, output continuity, research quality, safety, activation, pre-flight, re-validation and final project closure). It is not a 20-phase-only checklist.

## Executive result

The repository is a substantial research-only Python/FastAPI foundation. It already contains separate Spot and Futures market-data providers/scanners, many reusable analysis services, data stores, REST endpoints, an MCP adapter, and automated tests. It is **not yet an implementation of either complete 20-phase master prompt**. The existing readiness service correctly reports zero phases completed and marks the overall process incomplete.

Do not replace the current project with a new application. Preserve its modules and extend them behind the existing provider/service/API boundaries. Keep Spot and Futures workflows separate while sharing only market-neutral utilities.

## Mandatory paired-phase execution gate (user-directed)

The two master prompts must advance in lockstep by phase number. This is a hard sequencing constraint, not a preference:

1. Complete **SPOT Phase 01** in full.
2. Complete **FUTURES Phase 01** in full.
3. Verify both Phase 01 implementations and tests. Only when both are accepted may Phase 02 begin.
4. Complete **SPOT Phase 02**, then **FUTURES Phase 02**; verify both before Phase 03.
5. Repeat this paired sequence through Phase 20.
6. Never start, implement, mark complete, or claim progress on Phase N+1 in either market while either SPOT or FUTURES Phase N remains incomplete.
7. Existing reusable code from later phases may be inspected to understand dependencies, but it must not be modified as later-phase implementation until its paired phase is reached. Bug fixes necessary to make the current paired phase work are allowed; unrelated later-phase enhancements are deferred.
8. A phase is complete only when every task and output required by both canonical prompts for that phase is implemented, tested, integrated, and its data limitations are explicitly represented. A green test suite alone is not proof that every prompt requirement is complete.
9. If one market's phase is blocked by unavailable data, credentials, external provider, or exchange limitation, stop the sequence at that phase. Do not skip it to progress the other market. Record the exact blocker and request only the input or access needed to resolve it.
10. Maintain a paired gate ledger with separate Spot and Futures statuses: NOT_STARTED, IN_PROGRESS, BLOCKED, or COMPLETE. The combined phase status is COMPLETE only when both are COMPLETE.
11. The next phase is unlocked only by the paired completion rule. No phase may be silently skipped, merged, or declared complete by inference.
12. At Phase 20, finish and verify both final reports before declaring the combined project finished.

### Current paired-phase position

- Current authorized phase: **PHASE 01 only**.
- SPOT Phase 01: IN_PROGRESS — current scanner covers eligible exchange symbols/tickers and returned book tickers, but its own output explicitly lists missing all-symbol order-book depth, recent-average volume surge and market-cap enrichment.
- FUTURES Phase 01: IN_PROGRESS — USD-M/COIN-M scanners exist, but all-contract depth, volume surge, relative strength, open-interest change and market-cap enrichment remain incomplete.
- Phase 02 is LOCKED until both Phase 01 checklists are complete and verified.
- No Phase 16 implementation is authorized at this stage. Any experimental Phase 16 work has been reverted/deferred; it must be revisited only after paired Phases 01–15 are accepted.

## Phase 01 paired completion checklist — the only active workstream

### SPOT Phase 01 — remaining acceptance criteria

- [x] Fetch Spot exchange information and the all-symbol 24-hour ticker list.
- [x] Enumerate trading symbols and exclude non-TRADING, stablecoin/stablecoin, fiat and leveraged-token pairs.
- [x] Capture last price, 24-hour percentage change and quote volume.
- [x] Capture returned best bid/ask spread where the all-book-ticker endpoint supplies it.
- [x] Consolidate duplicate base assets across quote pairs; do not compare raw quote volumes across unlike quote assets.
- [x] Expose onboarding date and identify recent listings.
- [ ] Maintain a per-symbol failure ledger with exact reason; current implementation exposes only an aggregate failed count.
- [ ] Collect full order-book depth for every eligible pair (or explicitly enumerate every failed/unavailable pair); best bid/ask alone is not depth.
- [ ] Calculate volume surge against a defined recent historical average for every eligible pair.
- [ ] Add market-cap enrichment from a verified source with timestamps, mapping confidence and missing-coverage accounting.
- [ ] Add verified risk-tag and delisting-announcement coverage; do not infer labels from symbol names.
- [ ] Add objective top-gainer, top-loser, unusual-price, unusual-volume and high-liquidity outputs with disclosed thresholds.
- [ ] Compare related Futures activity as optional sentiment context without allowing Futures metrics to replace Spot data.
- [ ] Record source-specific retrieval timestamps, freshness, API/rate-limit failures and exact scan coverage.
- [ ] Do not mark SPOT Phase 01 complete until all applicable tasks are integrated and tests cover complete, partial and failed market coverage.

### FUTURES Phase 01 — remaining acceptance criteria

- [x] Scan each Futures family through its own exchange metadata and 24-hour ticker provider (USD-M and COIN-M are separate market families).
- [x] Include active perpetual and dated contracts by default; preserve contract type and delivery metadata.
- [x] Exclude non-TRADING contracts and support an optional narrowed quote/perpetual filter; the paired full-market run must not use those narrowing filters.
- [x] Capture 24-hour price change, volume, spread where returned, mark/index price, basis, funding and funding-interval metadata where available.
- [x] Preserve COIN-M margin/settlement asset and fixed USD contract face value metadata.
- [x] Consolidate duplicate underlying assets and avoid comparing unlike quote/margin units as if directly comparable.
- [x] Identify newly onboarded contracts.
- [ ] Maintain per-contract failure and exclusion reason ledgers across both USD-M and COIN-M.
- [ ] Collect full order-book depth for every eligible contract.
- [ ] Calculate volume surge versus recent average for every eligible contract.
- [ ] Collect Open Interest and comparable historical Open Interest change for every eligible contract in both market families, or explicitly account for endpoint limitations.
- [ ] Calculate relative strength versus BTC on a comparable quote/price basis for every eligible contract.
- [ ] Add verified market-cap enrichment and unique-underlying mapping.
- [ ] Add verified risk-tag and delisting-announcement coverage.
- [ ] Produce top gainers, top losers, unusual price/volume activity and high-liquidity outputs with disclosed thresholds.
- [ ] Integrate Spot reference/basis comparison as reference-only data, retaining Futures contract prices for Futures analysis.
- [ ] Preserve leverage brackets, maintenance tiers and symbol filters where official endpoints provide them; disclose per-contract gaps.
- [ ] Record per-endpoint timestamps, freshness, API/rate-limit failures and exact USD-M / COIN-M scan coverage.
- [ ] Do not mark FUTURES Phase 01 complete until both USD-M and COIN-M requirements applicable to the prompt are integrated and tested.

### Paired Phase 01 release gate

- SPOT Phase 01 status: **IN_PROGRESS**
- FUTURES Phase 01 status: **IN_PROGRESS**
- Combined Phase 01 status: **INCOMPLETE — PHASE 02 LOCKED**
- Required evidence to unlock Phase 02: implementation checklist complete for both prompts, automated tests passing, API responses showing exact totals/eligible/scanned/failed/excluded counts, explicit missing-data records, source timestamps, and a review confirming no eligible pair/contract was silently skipped.

## Phase-by-phase capability audit

| Phase | SPOT prompt | FUTURES prompt | Main gap / next work |
|---|---|---|---|
| 01 Complete market scan | PARTIAL | PARTIAL | Full symbol/ticker enumeration exists. Spot has 24h relative strength vs BTC; Futures scans USD-M and COIN-M separately and reports contract metadata. Both still lack all-pair order-book depth, recent-average volume surge, market-cap enrichment and complete risk-tag coverage. Futures lacks all-contract OI change and relative-strength enrichment. |
| 02 Global news intelligence | PARTIAL | PARTIAL | Configured RSS/Atom collection exists. It is not a complete global web search or a separate full-name/ticker/source sweep for every shortlisted coin. |
| 03 News verification / catalysts | PARTIAL | PARTIAL | Cross-domain title similarity and conservative keyword catalyst triage exist. Primary-claim verification, semantic duplicate handling, original-source adjudication and the prompt's weighted catalyst scoring are not complete. |
| 04 Initial filtering | PARTIAL | PARTIAL | Basic exchange eligibility, ticker validity and optional volume filtering exist. The complete objective screening funnel, staged N/M candidate ledger and documented rejection reasons are not integrated. |
| 05 BTC / global market | INCOMPLETE | INCOMPLETE | A limited BTC/ETH context endpoint exists. BTC dominance, total market cap, external sentiment indices and a verified macro/event calendar are not integrated. |
| 06 Deep technical analysis | PARTIAL | PARTIAL | EMA/SMA, RSI, MACD, Bollinger, support/resistance, Fibonacci, VWAP, volume profile and market-structure utilities exist. They are not assembled into the full requested six-timeframe per-candidate analysis pipeline. |
| 07 Liquidity / derivatives | PARTIAL | PARTIAL | Spot order-book, spread and Spot/Futures basis components exist. USD-M funding, OI, ratios, order flow and liquidation snapshots exist; COIN-M market data is partially supported. Full candidate-by-candidate depth, cost, funding-interval, leverage-tier and liquidation validation is incomplete. |
| 08 On-chain | PARTIAL | PARTIAL | Configured EVM RPC, token-transfer and wallet evidence exists. This is not universal multi-chain coverage; absent provider configuration blocks useful on-chain claims. |
| 09 Fundamentals / tokenomics | BLOCKED | BLOCKED | No complete project fundamentals, supply/unlock, competitor and roadmap provider pipeline. |
| 10 Whale / smart money | PARTIAL | PARTIAL | Configured EVM wallet and transfer evidence exists. Broad wallet coverage and reliable identity attribution are not established. |
| 11 Exchange flows | PARTIAL | PARTIAL | Configured wallet transfer flows can be summarized. Complete exchange reserves, comprehensive exchange labels and full-market flows are unavailable. |
| 12 Manipulation detection | PARTIAL | PARTIAL | Some order-flow, liquidity and anomaly evidence exists. It is not a validated comprehensive manipulation detector and must not be represented as proof of manipulation. |
| 13 Multi-timeframe confirmation | PARTIAL | PARTIAL | Spot multi-timeframe and Futures derivatives/order-flow multi-timeframe components exist. The full 5m/15m/1h/4h/1d/1w technical confirmation and unified final-candidate gate are not wired. |
| 14 Historical validation | INCOMPLETE | PARTIAL | Stored USD-M snapshot forward-outcome evaluation exists, but explicitly is not an execution-aware strategy backtest. A complete Spot and Futures backtesting system with fees, funding, slippage, liquidation, out-of-sample and regime validation is missing. |
| 15 Probability / forecasting | BLOCKED | BLOCKED | No validated forward predictive model is established. Statistical probabilities must remain NOT ESTABLISHED. |
| 16 Risk / sizing / timing | PARTIAL | PARTIAL | Spot and linear USD-M risk arithmetic and signal-lifecycle validation exist. Liquidation price is withheld without exchange margin tiers and account settings. COIN-M inverse contract risk arithmetic was started on the audit branch; it requires explicit contract face value, settlement asset and coin-denominated capital for sizing. Timing utility validates supplied windows but does not forecast them. |
| 17 Final selection / ranking | BLOCKED | BLOCKED | No complete weighted candidate ranking, one-coin/one-contract selection, correlation or portfolio risk engine. |
| 18 Independent red-team | BLOCKED | BLOCKED | No independent counter-thesis workflow is wired into the backend. |
| 19 Final signal audit | BLOCKED | BLOCKED | No complete per-signal live refresh, entry-condition recheck and expiry/invalidation audit pipeline. |
| 20 Final report | BLOCKED | BLOCKED | No end-to-end 20-phase report orchestrator with the complete prompt-specific output structure. |

## Important Spot / Futures separation requirements

### SPOT
- Spot is the only execution/research market in Master Prompt 01.
- Futures/derivatives may be shown only as optional read-only sentiment context.
- Spot trade planning must remain LONG-only; do not apply Futures short logic to Spot.
- Do not use a Futures price, stop, funding or liquidation value as a Spot trade level.

### FUTURES
- USD-M is the primary Futures market; COIN-M is included where supported and relevant.
- Keep USD-M linear and COIN-M inverse contract calculations separate.
- Carry contract type, delivery date, margin/settlement asset, contract filters, funding interval and contract-specific price basis with each plan.
- Do not claim a COIN-M liquidation price until leverage, margin mode, maintenance tier and applicable exchange data are available.
- Spot prices are reference-only and must not replace the selected Futures contract's prices.

## Confirmed architecture to preserve

- Python 3.11+ / FastAPI backend.
- Separate Binance Spot and Binance Futures provider adapters.
- Existing scanner, indicator, derivatives, order-book, news, on-chain, historical storage, risk, lifecycle and data-quality services.
- REST API and private read-only MCP adapter.
- Existing tests and GitHub Actions workflow.
- Research-only safety boundary: no order placement, cancellation, modification, withdrawals or wallet signing.

## First implementation sequence

1. [BRANCH IMPLEMENTED — CI VALIDATION PENDING] Add COIN-M inverse risk arithmetic; expose Binance COIN-M contract face value and settlement asset from scanner results.
2. [BRANCH IMPLEMENTED] Add the canonical Master Prompt 02 file to \`master-prompts/\` from the uploaded source text.
3. Implement a market-aware 20-phase orchestration contract that keeps SPOT and FUTURES phase status separate and never upgrades an incomplete phase to completed.
4. Complete Phase 01 Stage-1 data coverage using rate-limit-aware collection, per-symbol failure accounting and explicit missing-metric reporting.
5. Integrate the Phase 02–07 candidate pipeline and enforce data freshness / source traceability.
6. Add the on-chain, tokenomics, historical validation, risk, ranking, red-team and final-audit capabilities in dependency order.
7. Build the final report only from persisted phase outputs; prohibit fabricated fields and retain BUY / WAIT / NO TRADE gates.

## Audit limitations

- This was a static repository review through the GitHub connector. It does not establish runtime correctness for every endpoint.
- A prior GitHub Actions run on the baseline commit completed successfully. That result does not validate the new audit-branch changes.
- Live Binance API connectivity, configured RSS feeds, EVM RPC access, persistent storage and each external AI client's MCP connection must be checked in the actual deployment environment.
- The user-uploaded Futures master prompt is the governing source. Do not silently substitute a shortened copy or treat the Spot prompt as the Futures specification.


## Scope completeness and restart rule

The complete project perimeter is now explicitly recorded in `docs/UNIVERSAL_PROJECT_SCOPE_AND_EXECUTION_CONTROL.md`, including every pre-phase setup section, all 20 SPOT/FUTURES phase pairs, all post-phase execution/evidence/safety/activation requirements, and final project closure. The reusable restart instructions are in `master-prompts/MASTER_RESUME_PROMPT.md`. Every future coding session must read both canonical prompts before reading the scope and audit, determine the earliest incomplete paired phase from repository evidence, and resume there. Current statuses remain SPOT Phase 01 IN_PROGRESS, FUTURES Phase 01 IN_PROGRESS, combined Phase 01 INCOMPLETE, Phase 02 LOCKED.


## Mandatory pre-coding audit gate

Before any further feature coding, inspect the implementation already written, compare it against both canonical prompts and the active Phase 01 acceptance criteria, run available tests/static/security checks, correct confirmed defects in scope, add regression tests, and document deferred later-phase issues. New Phase 01 feature coding is permitted only after this audit gate is recorded COMPLETE or exact blockers are documented. The current phase authorization remains Phase 01 only.


## Session restart audit — 2026-11-11 (GitHub branch review)

### Repository state verified
- Repository: `mamunfb/universal-binance-ai-backend`.
- Work branch: `work/dual-master-prompt-audit`.
- Verified code-fix checkpoint: `721425b3b4f9eed02cf329d99b1a1bbca6e8e39d`.
- Base branch: `main`, base SHA `dfef59340c08fd20ba858efb78016ff8ff4e3997`; comparison showed the work branch ahead by 21 commits and not behind at the time of comparison.
- PR #1 remains OPEN and DRAFT; no merge or main-branch update was performed.
- GitHub Actions run `42926461113` on the verified checkpoint completed successfully: dashboard JavaScript syntax check passed; `pytest -q` reported **525 passed, 2 warnings**.
- The GitHub connector exposes remote commits/files but not a local working-tree status. Local uncommitted changes therefore remain UNVERIFIED, not assumed clean.

### Code and test areas inspected
- Canonical Spot/Futures prompts, complete scope, resume controller and existing implementation audit.
- Spot/Futures provider adapters, Spot/Futures scanners, market scan routes and combined scan accounting.
- Application configuration, environment example, API authentication/error middleware, startup/shutdown lifecycle and research pre-flight/readiness routes.
- Risk/qualification/data-quality services, RSS and EVM providers, dashboard rendering, MCP adapter and selected background stream collectors.
- Spot/Futures provider and scanner tests, dashboard markup tests, API error-envelope tests and MCP contract tests.
- Repository tree, CI workflow, PR metadata, branch commit and workflow job logs.

### Confirmed defects corrected before any new Phase 01 feature work
1. **P2 — Boolean volume threshold accepted by Futures scanner.** `scan_futures_markets` converted `True`/`False` to numeric values and did not reject them, unlike the Spot scanner. Added an explicit Boolean rejection in `backend/app/services/futures_scanner.py` and regression coverage in `tests/test_futures_scanner.py`.
2. **P2 — Unsafe dashboard HTML interpolation.** API-derived strings and serialized response details were inserted into `innerHTML` without consistent escaping. Added `escapeHtml` at the affected evidence, metrics, saved-snapshot, price-path and performance-report rendering points, including option attributes and JSON displayed inside HTML. Added regression assertions in `tests/test_dashboard_quality_markup.py`.

### Regression verification
- GitHub Actions on checkpoint `721425b3b4f9eed02cf329d99b1a1bbca6e8e39d`: **SUCCESS**.
- Dashboard JavaScript syntax check: **PASSED**.
- Full configured test suite: **525 passed, 2 warnings**.
- The two warnings are dependency deprecations; no test failures were reported.
- The earlier intermediate dashboard commit `b62bb4484c13ca2a30c81b42bab2722efd26ab8` failed the JavaScript syntax check due to a malformed concatenation introduced during escaping. That intermediate defect was corrected before the verified checkpoint; the later syntax check and test suite passed.

### Suspected risks, deferred findings and blockers
- **DEFERRED / Phase 07 background collection:** `.env.example` names `AGG_TRADE_COLLECTOR_JOBS`, while the Settings field maps to `AGGREGATE_TRADE_COLLECTOR_JOBS`. This configuration-documentation mismatch must be reconciled when the collector configuration/operations work is authorized; it was not changed as Phase 01 feature work.
- **UNVERIFIED security concern:** Spot scanner upstream exception text is returned from `str(exc)`. Review whether a configured custom base URL or transport exception can expose credentials/query data before changing the error contract.
- **Phase 01 still INCOMPLETE:** no per-symbol/per-contract failure ledger with exact reasons; no all-eligible-pair/contract depth; no recent-average volume surge; no verified market-cap/risk-tag/delisting coverage; no complete objective activity ranking; and no source-specific retrieval timestamp/freshness ledger.
- Futures Phase 01 also lacks all-contract Open Interest change and comparable relative-strength coverage; current output explicitly lists missing metrics.
- The CI workflow does not run Ruff, a type checker or a dedicated security scanner. Those checks were not executed locally in this session.
- Live Binance connectivity and deployment-environment capabilities were not tested from the GitHub source review.
- Local working-tree status is not available through the connected GitHub interface.

### Current paired phase decision
- SPOT Phase 01: **IN_PROGRESS**.
- FUTURES Phase 01: **IN_PROGRESS**.
- Combined Phase 01: **INCOMPLETE**.
- Phase 02: **LOCKED**.
- No later-phase feature was implemented or unlocked.
- **Pre-Coding Full Audit: INCOMPLETE.** Confirmed in-scope correctness/security defects found in the inspected areas were fixed and regression-tested, but the exhaustive review of every existing service/module and local/deployment runtime state is not yet evidenced. Do not begin new Phase 01 feature implementation until the remaining audit coverage and limitations are resolved or explicitly accepted as blockers.


## Continued audit checkpoint — scanner security and documentation review

### Additional confirmed defect corrected
3. **P2 — Spot scanner exception leakage.** `backend/app/services/market_scanner.py` returned `str(exc)` when the Spot provider failed. A configured custom endpoint or transport error could include a URL/query value in the exception text. The response now returns a stable `UPSTREAM_UNAVAILABLE` code, a fixed message and exception type only. Regression test `test_scan_reports_upstream_failure_without_fabricating_zero_market_result` now injects a token-bearing URL and asserts the token is not returned.
- Code commit: `75bd2d3affa7877fcdd5be58ef5f524e33e9f71f`.
- Regression test commit: `898b21e731ad15e9636ae401bb652abf03a2ea8d`.
- GitHub Actions run `42926963128` on that code/test checkpoint: **SUCCESS**, dashboard JavaScript syntax passed, **525 passed, 2 warnings**.

### Documentation contract corrections
- `docs/API.md`: Spot scanner's omitted quote filter means all quote assets, not USDT only.
- `docs/FUTURES_API.md`: default scan includes all active TRADING contract types, including dated contracts; perpetual-only is an explicit narrowing filter. COIN-M derived notional is explicitly distinguished from native exchange quote volume.
- `README.md`: Futures scanner coverage description corrected to include currently trading perpetual and dated contracts.
- Documentation commits: `f9b5fa24ae7621c753c1efdbfb92a526343b00de`, `91a73c713b6bb3a62352158fc0d357cb076ae08a`, `339788dae314ee22af4764fb5c487e7fe07c6f4d`.

### Expanded repository inventory / audit evidence
- Enumerated the recursive repository tree and inventoried all backend providers, service modules, 84 FastAPI route declarations, MCP tool registrations, configuration files, Dockerfile, CI workflow and test modules.
- Reviewed market scanner/provider contracts and selected storage/collector paths, including SQLite validation/idempotency, environment configuration, API authentication/error handling, background-task lifecycle and MCP request handling.
- The MCP server has one persistence action, `save_market_confluence_snapshot`, routed through POST to local SQLite. It does not place/cancel/modify trades or withdraw funds, but it means the MCP surface is not strictly read-only in the literal sense. **DEFERRED / architecture acceptance review:** decide whether this local snapshot-save action is acceptable under the final read-only MCP requirement or should be moved outside MCP.
- **P2 / API resilience gap:** Spot and Futures REST provider adapters currently apply request timeouts but do not implement a shared retry/backoff or explicit rate-limit/Retry-After policy. Phase 01 must disclose upstream rate-limit outcomes and must not silently turn them into complete scans. The integration architecture acceptance item remains open.
- `docs/FUTURES_API.md` previously claimed the COIN-M ticker exposed quote volume, while the implementation derives a notional proxy from baseVolume × lastPrice when quoteVolume is absent. Documentation now describes the derivation and unit caveat; this derived metric still needs explicit product acceptance and source/units evidence before being used for cross-market ranking.
- Existing tests cover Spot/Futures scanner normal, missing-ticker, malformed-response and upstream-failure cases, but do not yet verify a per-symbol reason ledger, missing book ticker accounting, or all-symbol depth completeness.

### Checks not run / still unverified
- Ruff is declared as a dev dependency in `pyproject.toml`, but the checked-in GitHub Actions workflow runs only dashboard JavaScript syntax and pytest. Ruff was not run locally because this remote repository interface does not provide a local checkout or shell in the repository workspace.
- Type checking and a dedicated security scanner are not configured in the workflow and were not executed.
- Live Binance endpoint/rate-limit behavior and intended deployment persistence/clock synchronization remain unverified.
- Remote GitHub operations cannot establish the user's local working-tree status; it remains UNVERIFIED.
- The audit has inventoried the codebase and reviewed high-risk paths, but a line-by-line acceptance review of every existing analysis/storage service and all 84 routes is not yet complete.

### Updated gate decision
- Confirmed Spot exception leakage fix: **FIXED + regression-tested**.
- Previous Futures Boolean validation and dashboard HTML escaping fixes remain **FIXED + regression-tested**.
- Spot Phase 01: **IN_PROGRESS**.
- Futures Phase 01: **IN_PROGRESS**.
- Combined Phase 01: **INCOMPLETE**.
- Phase 02: **LOCKED**.
- Pre-Coding Full Audit: **INCOMPLETE**. Do not start new Phase 01 feature implementation until remaining code review, static/security checks and runtime limitations have been completed or explicitly recorded as accepted blockers.


## Further security and static-analysis review — 2026-11-11

### Additional confirmed exception-disclosure defects corrected
4. **P2 — Market-data API routes exposed raw provider exception messages.** The USD-M/COIN-M kline routes and Spot kline/technical-analysis/support-resistance/volume-structure routes returned `str(exc)` in HTTP 502 details. They now return `UPSTREAM_UNAVAILABLE` and exception type only. Added regression coverage for Spot, USD-M and COIN-M klines plus Spot technical analysis.
5. **P2 — Cross-chain intelligence exposed raw RPC/config exception text.** The combined cross-chain token intelligence response included exception text in its per-chain entity-flow and wallet-concentration errors. It now returns the stable `UPSTREAM_UNAVAILABLE` marker. Added a regression test with a token-bearing RPC URL.
6. **P2 — RSS source failures exposed feed URL details.** `RSSNewsProvider.collect` included raw HTTP exception text in source failure records. It now records the exception type only. Added a regression test using a token-bearing feed query parameter.

The Spot scanner, Futures Boolean filter, dashboard HTML rendering, market-data route error handling, cross-chain intelligence error handling and RSS error handling fixes are all restricted to error disclosure, input validation or rendering safety; no trading execution capability was added.

### Static analysis
- Added a Ruff CI step on the work branch.
- Initial broad `ruff check backend tests mcp-server` reported **289 diagnostics**, with 187 marked auto-fixable. This is an existing repository-wide lint debt finding; the step was narrowed to Ruff's core correctness rules `E4,E7,E9,F` for the next verification run. Import sorting and Bugbear-style findings from the broad run are not yet remediated.
- Type checking and dedicated security scanning remain unavailable in the current workflow.

### Verification status
- Spot scanner exception fix checkpoint: `898b21e731ad15e9636ae401bb652abf03a2ea8d` — CI SUCCESS, 525 passed.
- Market-data route sanitization checkpoint: `03c49676d3d6a839cbf211010e77b24478af7cfb` — CI SUCCESS, 526 passed.
- RSS sanitization checkpoint: `f35e8a777c46cbc6e0bc6e840e4b81597a17318b` — CI SUCCESS, 527 passed.
- Cross-chain sanitization test initially failed because its fake chain fixture omitted the required `status` field; the fixture was corrected in `75a0a5da36a57a9f3964ae8a5aa291e868fe9b94`. A successful full CI run for that corrected checkpoint is still pending.
- Ruff broad check failed with 289 diagnostics; narrowed core-rule check and full test run for the latest workflow revision are pending.

### Updated gate decision
- Confirmed exception-disclosure defects in the reviewed market-data, RSS and cross-chain paths: **FIXED; final CI re-verification pending for the latest combined checkpoint**.
- SPOT Phase 01: **IN_PROGRESS**.
- FUTURES Phase 01: **IN_PROGRESS**.
- Combined Phase 01: **INCOMPLETE**.
- Phase 02: **LOCKED**.
- Pre-Coding Full Audit: **INCOMPLETE**. No Phase 01 feature implementation is authorized until latest CI passes and remaining route/service, persistence, runtime, static-analysis and security coverage gaps are resolved or documented as blockers.


## Verified combined security-fix checkpoint — 2026-11-11

- Latest verified code/test checkpoint: `dcfb8faf5372c0a9f75088d9e7f79afb9b2c42c7`.
- GitHub Actions run `42927721586`: **SUCCESS**.
- Ruff core rules on reviewed security and Phase 01 files: **PASSED**.
- Dashboard JavaScript syntax check: **PASSED**.
- Full pytest suite: **528 passed, 2 warnings**.
- The regression set includes Futures Boolean volume filter rejection, dashboard HTML escaping, Spot scanner exception sanitization, market-data API exception sanitization, cross-chain exception sanitization and RSS feed URL sanitization.
- A dedicated paired phase ledger now exists at `docs/PAIRED_PHASE_LEDGER.md` and records SPOT/FUTURES Phase 01 as IN_PROGRESS, Combined Phase 01 INCOMPLETE, Phase 02 LOCKED.

### Lint scope qualification
- The full-repository broad Ruff scan previously reported 289 diagnostics (including import sorting, Bugbear and test-style findings).
- The passing CI Ruff command intentionally covers core correctness rules `E4,E7,E9,F` on the reviewed security and Phase 01 files. It is **not** evidence that the entire repository is lint-clean.
- Remaining broad lint debt is documented and must be handled in a dedicated quality pass; it does not authorize Phase 01 feature coding while the full pre-coding audit remains incomplete.

### Gate status
- Latest code checkpoint CI: **PASS**.
- Pre-Coding Full Audit: **INCOMPLETE** — the latest checks pass, but line-by-line review of all 84 routes and every existing analysis/storage service, deployment/live-provider verification, full-repository static analysis and dedicated security scanning are not yet complete.
- SPOT Phase 01: **IN_PROGRESS**.
- FUTURES Phase 01: **IN_PROGRESS**.
- Combined Phase 01: **INCOMPLETE**.
- Phase 02: **LOCKED**.


## Collector data-integrity audit — 2026-11-11

### Confirmed defect corrected
7. **P2 — Liquidation stream accepted malformed/non-finite numeric fields.** normalize_force_order converted q and l outside its guarded parse block and accepted NaN/Infinity for parsed numeric quantities. A malformed event could terminate the current receive loop and reconnect the collector, or persist non-finite values into SQLite. The normalizer now parses all four quantity/price fields inside one guarded block, rejects non-finite and negative values, and rejects negative event/trade timestamps. Regression coverage includes malformed q/l, NaN, Infinity, negative quantities and negative timestamps.
- Service commit: eb81805b126ab0cd65cf01f6cbae2d378ba6e11c.
- Regression-test commit: d560bd5bb803c25cec15b6d2d5756a1086bb8d28.
- GitHub Actions run 42928650029 on test checkpoint d560bd5bb803c25cec15b6d2d5756a1086bb8d28: **SUCCESS**; Ruff step passed, dashboard JavaScript syntax passed, pytest **530 passed, 2 warnings**.
- The first workflow run on service-only commit eb81805b126ab0cd65cf01f6cbae2d378ba6e11c also passed, but the test commit's run is the relevant verification for the added regression cases.

### Additional audit observations
- liquidation_collector.last_error still stores str(exc) in its status object. Its current websocket URL is a fixed public Binance stream URL (no configured credential/query token); this is not presently confirmed as a secret disclosure, but the raw diagnostic remains a data-minimization concern for a later collector-observability review.
- The latest passing Ruff command did not yet include the newly changed liquidation collector and its test. The CI Ruff file list has now been expanded to include both; that workflow change requires its own passing run before claiming lint coverage for these files.
- The audit remains static/remote. No live Binance stream or deployment database test has been performed.

### Gate decision
- Liquidation numeric normalization: **FIXED + regression-tested**.
- Latest test checkpoint: **530 passed, 2 warnings** at d560bd5bb803c25cec15b6d2d5756a1086bb8d28.
- Pre-Coding Full Audit: **INCOMPLETE**.
- SPOT Phase 01: **IN_PROGRESS**; FUTURES Phase 01: **IN_PROGRESS**; Combined Phase 01: **INCOMPLETE**; Phase 02: **LOCKED**.


## Persistence validation and EVM error-disclosure audit — 2026-11-11

### Confirmed defects corrected
8. **P2 — Market-confluence snapshot storage accepted Boolean/fractional numeric values.** Python numeric coercion allowed JSON Boolean values to pass as timestamps/prices and truncated fractional timestamps through int conversion. The store now rejects Boolean timestamps/prices, fractional timestamps, invalid nested object shapes, negative close timestamps and future reference-candle close times. Added parametrized regression coverage and retained idempotent save/history tests.
9. **P2 — EVM transfer indexer returned raw provider exception text.** The indexer included up to 300 characters of exception text in its response. HTTP transport exceptions may contain request URL details, and provider JSON-RPC error payloads are externally controlled. The error response now returns the stable UPSTREAM_UNAVAILABLE code and exception type only. Added a token-bearing fake RPC exception regression test.
- Snapshot store fix: 984faaf23d4caa52003304fb6f879a0d6ebccd5d.
- Snapshot regression tests: a3c911eb96f050fc62107a59f0b060f658137664.
- EVM indexer sanitization: 0a24b0c8de4a0fc6d26a7d75325a8f4f108022e8.
- EVM regression test: fa44bb6792d7a72670189ef7f353a1f5b1bb3e76.
- Ruff target list expanded to include the changed storage modules and tests at 4e406ad4a04a9ac3ce0656d6d83b55fdf5e348fa. The latest CI result for this expanded workflow is pending at the time of this entry.

### Additional persistence/lifecycle review notes
- SQLite stores inspected in this pass use parameterized SQL values and context-managed sqlite3 connections; reviewed UPSERT/unique-key paths provide idempotency where designed. This is not a claim that every storage module has been exhaustively reviewed.
- Historical and derivatives collectors use sequential job execution, bounded configured job counts, task cancellation/stop hooks and sanitized exception-type status. Order-book and aggregate-trade collectors expose per-job task handling and exception-type status; their full concurrency/reconnect semantics still require line-by-line review.
- EVM transfer index coverage is recorded only after a successfully parsed chunk is persisted. Existing range-coverage logic reports gaps and overlapping coverage; full reorg/removed-log lifecycle and deep-reorg behavior remain runtime/provider acceptance items.
- EVM RPC provider has a bounded retry loop for selected HTTP status codes and transport errors, but Binance Spot/Futures provider adapters still lack a shared retry/Retry-After policy.
- No live RPC, Binance websocket, SQLite crash-recovery, multi-process writer or deployment-volume test was executed in this remote source audit.

### Gate decision
- Snapshot numeric validation: **FIXED + regression tests added; CI pending**.
- EVM indexer error disclosure: **FIXED + regression test added; CI pending**.
- Pre-Coding Full Audit: **INCOMPLETE**.
- SPOT Phase 01: **IN_PROGRESS**; FUTURES Phase 01: **IN_PROGRESS**; Combined Phase 01: **INCOMPLETE**; Phase 02: **LOCKED**.


### Additional EVM API input-validation correction — 2026-11-11
10. **P2 — EVM history index route coerced JSON Boolean/fractional block values.** The route previously applied int() directly to request-body fields, which accepted true as 1 and truncated fractional numbers. It now requires from_block, to_block and chunk_size to be JSON integers (Boolean is explicitly rejected) before any provider call. Added direct route regression tests for all three malformed cases.
- API fix: c791d00262211141a45b2bf0ab0f1b777e13c27c.
- Regression test: 6a19418c531913e83a93a55479c3ff3c0ca9d746.
- CI for the expanded persistence/EVM Ruff and regression suite is being rerun on the latest branch head; earlier runs correctly failed at Ruff before reaching pytest due to a pre-existing semicolon in the snapshot test, which has since been reformatted. Do not treat those failed runs as test failures.


## Verified persistence and EVM validation checkpoint — 2026-11-11

- Verified code/test checkpoint: `6a19418c531913e83a93a55479c3ff3c0ca9d746`.
- GitHub Actions run `42929655489`: **SUCCESS**.
- Ruff core checks on the reviewed security/storage/API files: **PASSED**.
- Dashboard JavaScript syntax: **PASSED**.
- Pytest: **537 passed, 2 warnings**.
- This checkpoint verifies the market-confluence numeric validation tests, EVM indexer exception sanitization test, and EVM route rejection tests for Boolean/fractional block values.
- Documentation/ledger commits after this code/test checkpoint are not themselves included in that run; the current docs HEAD requires its own CI result.

### Current audit boundary
- Pre-Coding Full Audit remains **INCOMPLETE**. The review has improved coverage of persistence and collector paths but has not completed a line-by-line acceptance review of every API route, analysis/storage module, MCP action, deployment/runtime setting or live provider behavior.
- SPOT Phase 01: **IN_PROGRESS**; FUTURES Phase 01: **IN_PROGRESS**; Combined Phase 01: **INCOMPLETE**; Phase 02: **LOCKED**.


## Audit continuation — verified latest HEAD and MCP/provider review (2026-11-11)

- Latest branch HEAD `be448172169bbb68d00c827f496eaab82780c598`: GitHub Actions run `42929783007` completed **SUCCESS**. The preceding audit documentation checkpoint `16c8fb27eabfd7d5392578e34464ecc51929e3f4` also has run `42929771515` **SUCCESS**. The separately verified code/test checkpoint remains `6a19418c531913e83a93a55479c3ff3c0ca9d746` with 537 passed / 2 warnings; do not infer that exact pytest count for later documentation-only HEAD without inspecting its job summary.
- Current-branch review of `mcp-server/server.py` confirms the MCP surface is **not literally read-only**: it exposes `save_market_confluence_snapshot`, which calls authenticated `_post()` to persist a descriptive snapshot to local backend storage. This is not a trade/order/wallet action, but the scope/audit wording “private read-only MCP adapter” is inaccurate. Architecture acceptance is OPEN: retain this narrow local research-evidence write with explicit documentation/consent, or remove it from MCP after user/architecture approval. No change made pending that decision.
- Both Binance REST adapters (`binance_spot.py`, `binance_futures.py`) currently issue one HTTP GET, call `raise_for_status()`, and return JSON; they do not implement a shared retry/backoff or explicit `Retry-After` / rate-limit policy. This remains an audit gap for complete-market scanning and is not silently treated as an implemented capability. No retry code added in this audit step.
- Static review of the MCP wrapper also shows the need for a systematic boundary-validation pass for Boolean-as-integer values on integer-annotated tool arguments; this is an audit item, not yet a confirmed exploitable API defect because framework-level input validation must be tested.
- PR #1 remains OPEN / DRAFT / unmerged; head `be448172169bbb68d00c827f496eaab82780c598`; branch comparison remains 77 ahead / 0 behind main. Main is unchanged.
- Pre-Coding Full Audit remains INCOMPLETE; Phase 01 SPOT and FUTURES remain IN_PROGRESS; Phase 02 remains LOCKED. No Phase 01 feature coding started.


## Confirmed production authentication defect — 2026-11-11

- Static route-middleware review found that when a strong owner key was configured in production, a shorter-than-32-character AI-client key could still authenticate: the production startup gate allowed the owner-key fallback, but the subsequent client-key matching loop did not enforce the minimum length.
- Fixed in `backend/app/main.py`: only AI-client keys of at least 32 characters are eligible for constant-time matching. A configured strong owner key remains usable as the intended fallback.
- Added regression test `test_production_rejects_weak_client_key_even_when_owner_key_is_configured`, which checks that the weak client key receives 401 while the strong owner key remains accepted.
- Code commit: `ffad59b3f906c49ffc539838a289357f18d3d548`; regression-test commit: `205c2fa2a36f72709748803c01de3e535c6b575e`. CI for the new test/code checkpoint must be checked before marking this fix verified.
- This is a confirmed existing security defect correction, not Phase 01 feature implementation.


## Authentication regression verification and API-route review — 2026-11-11

- CI run `42931082393` for regression-test commit `205c2fa2a36f72709748803c01de3e535c6b575e`: **SUCCESS**. Ruff targeted core checks passed; dashboard JavaScript syntax passed; pytest **538 passed, 2 warnings**. The two warnings are upstream deprecations (Starlette/httpx TestClient and FastAPI `example` parameter); Node reports punycode/Node 20 action deprecations.
- Documentation-only HEAD `797f5c844bdf1f2f3343386418e76c3ed333cf95` CI run `42931109389`: **SUCCESS**. The 538 test count is from the preceding code/test checkpoint, not a separately inferred count for the docs-only commit.
- Continued static review of `backend/app/main.py`: 80 route decorators were enumerated. Reviewed authentication middleware, standardized validation/unhandled error handlers, market scan and preflight routes, EVM history indexing, market-confluence persistence, derivatives collection/history endpoints, and market-data quality/history endpoints. This is a route inventory plus targeted review, not a completed line-by-line audit of all 80 handlers.
- Provider review reconfirmed Spot and Futures REST adapters have 15-second default timeouts and response-shape checks on many endpoints, but no common retry/backoff or Retry-After policy. No live Binance request was performed.
- Existing API auth behavior remains: authentication is enforced on `/api/*` when a key is configured; production fails closed if neither a valid client-key configuration nor a strong owner key is available. `/health` remains outside the private API middleware by design.
- Full audit gate remains INCOMPLETE; paired Phase 01 remains IN_PROGRESS on both Spot and Futures; Phase 02 remains LOCKED. No Phase 01 feature coding started.


## Order-book sequence synchronization correction — 2026-11-11

- Review of `OrderBookStreamCollector._validate_sequence` found the initial Futures snapshot bridge reused the Spot `lastUpdateId + 1` rule and did not verify the Futures `pu` link on the first accepted event. That could accept a first Futures diff event with `U == lastUpdateId + 1` even when `pu` did not equal the snapshot ID, allowing a missed update gap to be treated as synchronized.
- Corrected initial USD-M/COIN-M validation to require either (a) the first event overlaps the snapshot ID (`U <= lastUpdateId <= u`) or (b) it directly continues from the snapshot (`pu == lastUpdateId`). Subsequent Futures events still require `pu == previous u`. Spot retains its separate `U <= lastUpdateId + 1 <= u` rule.
- Added strict integer validation for `U`, `u`, and Futures `pu` so booleans/fractional values are not truncated into plausible sequence numbers. Added regression coverage for overlap, direct continuation, an unbridged gap, malformed IDs, and unchanged Spot rules. Updated an older Futures fixture to include the required `pu` field.
- CI checkpoint `d4b4820d6c1d3a7c94716608fce00eaf55139cb9`, run `42932203177`: **SUCCESS**; targeted Ruff checks passed including `order_book_stream.py` and `test_order_book_stream.py`; dashboard JS syntax passed; pytest **548 passed, 2 warnings**.
- Intermediate CI attempts exposed two test-harness issues (legacy Futures fixture omitted `pu`; newly linted test contained an unused import). Both were corrected; the final checkpoint above is green.
- Protocol references reviewed: Binance COIN-M Futures diff-depth event schema documents `U`, `u`, and `pu` (https://developers.binance.info/en/docs/catalog/core-trading-derivatives-trading-coin-m-futures/api/ws-streams); Binance Spot's official WebSocket stream documentation describes the separate Spot snapshot-bridge rule (https://github.com/binance/binance-spot-api-docs/blob/master/web-socket-streams.md).
- No live WebSocket connection was performed. Full Pre-Coding Audit remains INCOMPLETE; this is a correctness fix to an existing collector, not Phase 01 feature coding.


## Order-book reader shutdown and bounded-queue correction — 2026-11-11

- Collector lifecycle review found the reader attempted to enqueue a termination sentinel in its finally block but silently ignored QueueFull. If the WebSocket ended while the bounded 20,000-event queue was full, the consumer could drain queued events and then wait indefinitely because it never received the stream-closed sentinel.
- Corrected shutdown behavior: when the queue is full, discard one buffered delta and enqueue the termination sentinel. This intentionally forces the consumer to exit/reconnect instead of processing a potentially incomplete local order book. The next connection obtains a fresh REST snapshot and re-synchronizes the stream.
- Added asynchronous regression tests for normal socket termination with a full queue and reader cancellation with a full queue.
- CI run 42933491101 on 29db479fb82cdd9a90b86f81300d15f9b8dc234c: SUCCESS; targeted Ruff checks passed; dashboard JavaScript syntax passed; pytest 550 passed, 2 warnings.
- Intermediate runs: 42933359688 failed because the new tests initially omitted the asyncio import; 42933385702 then exposed that the cancellation test needed to gather the expected cancelled task rather than await it as a successful completion. Both test-harness issues were corrected before the successful run above.
- No live WebSocket test or real queue-saturation integration test against Binance was performed. Full Pre-Coding Audit remains INCOMPLETE; this is a collector correctness fix, not Phase 01 feature coding.


## Order-book REST snapshot sequence-ID validation — 2026-11-11

- Continued review found the order-book collector coerced the REST snapshot lastUpdateId through int(), which could silently truncate a fractional value or accept a Boolean as an integer before diff-stream sequence checks began.
- Added strict snapshot update-ID validation: only a non-Boolean Python integer is accepted; malformed values cause an explicit DEPTH_INVALID_SNAPSHOT_UPDATE_ID reconnect path. Added regression tests for fractional, Boolean, string, and valid integer inputs.
- CI run 42933697618 on 716709c26781b52300dc77188161196962a268a5: SUCCESS; targeted Ruff checks passed; dashboard JavaScript syntax passed; pytest 554 passed, 2 warnings.
- No live REST snapshot or WebSocket exchange call was performed. This is an existing collector correctness fix; full Pre-Coding Audit remains INCOMPLETE and no Phase 01 feature coding has started.


## Repository resume audit — 2026-11-11 (HEAD 21484ddb0bf4a4c7c6ec83279930546b4535405b)

### Current GitHub evidence
- Work branch: `work/dual-master-prompt-audit`; repository default branch: `main`.
- PR #1: OPEN / DRAFT / unmerged; base `main`; head `21484ddb0bf4a4c7c6ec83279930546b4535405b` at the start of this audit checkpoint.
- Branch comparison: 104 ahead / 0 behind main. Main was not modified.
- Latest workflow run at that HEAD: `42933836840`, job `130238866712`, SUCCESS. Job steps confirm dependency installation, targeted Ruff, dashboard JS syntax and pytest all succeeded. Log result: `554 passed, 2 warnings`; warnings include Starlette/httpx TestClient and FastAPI parameter deprecations. Node also emitted a punycode deprecation and GitHub runner action Node 20 deprecation notice.
- GitHub connector does not expose a local working-tree status; local changes remain UNVERIFIED.

### Current-session inspection
- Read the complete canonical SPOT and FUTURES master prompt files, project scope, implementation audit and paired phase ledger from the work branch.
- Rechecked current Spot/Futures provider adapters, Spot/Futures scanner services, scanner test modules and GitHub Actions workflow.
- Enumerated 80 FastAPI route decorators in `backend/app/main.py` and inventoried 54 provider/service source files. This is an inventory, not a claim that every route/service has been line-by-line audited.
- Confirmed the Phase 01 scanner gaps remain as documented: exact per-symbol/per-contract failure and exclusion reasons; full depth collection or exact per-symbol unavailability; recent-average volume surge; market-cap enrichment; verified risk-tag/delisting evidence; objective activity rankings; and source-specific timestamps/freshness. Futures additionally requires complete USD-M/COIN-M OI change and comparable BTC relative-strength coverage.
- Spot and Futures adapters still create a fresh HTTP client per request, apply a 15-second default timeout and do not yet share an explicit retry/backoff / Retry-After policy. Do not interpret a green test suite as proving upstream rate-limit resilience.

### Gate decision and restrictions
- CI at current HEAD: PASS (554 tests, 2 warnings; targeted Ruff and dashboard syntax checks passed).
- Pre-Coding Full Audit: INCOMPLETE. The line-by-line review of all 80 routes and 54 provider/service modules is not complete. Live Binance/deployment checks, type checking and dedicated security scanning are not available as verified evidence in this remote review. MCP `save_market_confluence_snapshot` architecture acceptance remains open from the prior audit.
- SPOT Phase 01: IN_PROGRESS; FUTURES Phase 01: IN_PROGRESS; Combined Phase 01: INCOMPLETE; Phase 02: LOCKED.
- No new Phase 01 feature coding is authorized until the mandatory audit gate is completed or exact unresolved items are formally resolved as blockers under the scope. This checkpoint changes documentation only; it does not claim phase acceptance.
- No trading order execution, cancellation, modification, withdrawal or wallet-signing capability was introduced.


## Binance REST retry/backoff correction — 4ecf7805578df40b6d80628144e100b454ace044 (2026-11-11)

### Finding and implementation
- Confirmed existing gap: Spot and Futures public REST adapters performed a single GET attempt and had no shared bounded retry/backoff or explicit handling of Binance `Retry-After`.
- Binance official Spot REST documentation states that HTTP 429 indicates a rate-limit breach, that clients must back off, that repeated violations can lead to HTTP 418 IP bans, and that `Retry-After` is supplied on 429/418 responses. Official reference: https://developers.binance.com/en/docs/products/spot/rest-api . The Binance Futures/general API documentation describes the corresponding 429/418 and IP-weight behaviour: https://developers.binance.com/en/docs/products/derivatives-trading-portfolio-margin-pro/general-info .
- Added market-neutral helper `backend/app/providers/http_retry.py` for idempotent GETs: bounded attempts; numeric and HTTP-date Retry-After parsing; exponential fallback for absent/invalid headers; bounded backoff for transport errors and HTTP 5xx; immediate stop on HTTP 418 to avoid another request during an IP ban.
- Integrated the helper into `BinanceSpotProvider._get` and `BinanceFuturesProvider._get`. Spot and Futures endpoints, symbols, calculations and response contracts remain separate.
- Added `tests/test_binance_http_retry.py` covering 429 Retry-After, 418 immediate stop, 503 retry, transport retry, missing-header backoff and HTTP-date parsing. Updated provider test doubles and expanded the CI Ruff target list to include the changed provider files and new tests.
- Commit: `4ecf7805578df40b6d80628144e100b454ace044` (`fix(api): honor Binance rate limits with bounded GET retries`).

### Verification status at documentation time
- GitHub Actions run `42957685379` for commit `4ecf7805578df40b6d80628144e100b454ace044` was IN_PROGRESS; no test or lint pass is claimed yet. Recheck the completed run and inspect its actual job log before accepting this correction.
- No live Binance 429/418 test was performed. Retry behaviour is fixture-tested only pending CI.
- The scanner does not yet expose a structured per-symbol retry/failure ledger; that remains a Phase 01 acceptance item.
- Pre-Coding Full Audit remains INCOMPLETE because the complete line-by-line review of all 80 API routes and 54 provider/service modules and the MCP architecture decision remain outstanding. This change fixes one confirmed shared API-reliability gap; it does not close the audit gate.
- SPOT Phase 01: IN_PROGRESS; FUTURES Phase 01: IN_PROGRESS; Combined Phase 01: INCOMPLETE; Phase 02: LOCKED.
- No order execution or wallet action was introduced.


## Verified provider retry/backoff regression checkpoint — 2026-11-11

- Code/test commit: `4ecf7805578df40b6d80628144e100b454ace044`.
- GitHub Actions run `42957685379`: **SUCCESS**; all job steps completed successfully.
- Actual job log confirms Ruff core checks passed on the new retry helper, both Binance REST providers and their tests; dashboard JavaScript syntax passed; pytest **560 passed, 2 warnings**.
- The two pytest warnings are Starlette/httpx TestClient and FastAPI parameter deprecations. Node also reports the punycode deprecation and GitHub action Node 20 deprecation notice.
- Retry tests passed for numeric Retry-After on 429, immediate non-retry on 418, 503 backoff, transport-error retry, bounded exponential fallback without Retry-After, and HTTP-date Retry-After parsing.
- Current branch documentation HEAD at the time of this entry: `6d3db66cb0a00f9f0f1f83776d18536b335cc857`, a docs-only commit after the verified code/test checkpoint. The exact 560-pass result is attributed to code/test commit `4ecf7805578df40b6d80628144e100b454ace044`, not the later docs-only HEAD.
- No live Binance rate-limit/IP-ban test was performed; external runtime behaviour remains unverified.
- Pre-Coding Full Audit remains **INCOMPLETE**: exhaustive line-by-line review of all 80 route decorators and 54 provider/service files has not been completed, and the MCP snapshot-save architecture decision remains open. Do not start new Phase 01 feature implementation until the audit gate is resolved.
- SPOT Phase 01: IN_PROGRESS; FUTURES Phase 01: IN_PROGRESS; Combined Phase 01: INCOMPLETE; Phase 02: LOCKED. No trading execution capability added.


## MCP input-boundary audit and correction — 2026-11-11

### Confirmed issue
- Reviewed all 80 FastAPI route decorators in `backend/app/main.py` as a route inventory and inspected authentication/error middleware, preflight, Spot/Futures scan endpoints, combined market scan, research snapshot persistence and representative data/history/analysis routes. This review does not certify every route's full implementation or all 54 provider/service modules.
- MCP adapter `mcp-server/server.py` exposes 38 tools. It has a fixed-path authenticated `_get` and one fixed-path authenticated `_post` used only by `save_market_confluence_snapshot`; the POST persists a descriptive local research snapshot and is not a Binance order endpoint. MCP is therefore read-only with respect to exchange trading, but not strictly read-only with respect to local research storage.
- Confirmed input-validation defect: Python Boolean values satisfy integer range checks because `bool` subclasses `int`. MCP tool arguments are untrusted, and range-only checks could accept values such as `True` for integer timestamps, limits or block/decimal parameters.

### Fix
- Commit `ae93896350a0cd4128a7a919bf32cace61582522`: added `_reject_boolean_integer_arguments`, using each tool's resolved type hints and signature to reject booleans for `int` and `int | None` parameters before tool logic.
- Applied the guard to all 38 MCP tool registrations, including tools without current integer parameters so future typed integer additions inherit the boundary guard.
- Added parameterized tests for Boolean Spot kline limit, historical timestamp, cross-chain decimals, aggregate-trade timestamp and local snapshot timestamp. Each test verifies rejection before any `_get` or `_post` call.

### Verification and remaining audit gate
- GitHub Actions run `42958954122` targets this code commit and was IN_PROGRESS at documentation time. No pass is claimed pending completion and review of actual logs.
- API route inventory: 80 route decorators. Full route-level behavioral/security acceptance remains subject to individual endpoint tests; inventory is not a substitute for test coverage.
- Provider/service inventory: 54 source modules. Complete line-by-line review remains INCOMPLETE. Dedicated type/security scans and live Binance/deployment checks remain unverified.
- MCP snapshot persistence architecture decision remains OPEN. Current behavior is documented as a local research-data write, not exchange trading execution.
- SPOT Phase 01: IN_PROGRESS; FUTURES Phase 01: IN_PROGRESS; Combined Phase 01: INCOMPLETE; Phase 02: LOCKED. No Spot/Futures scanner feature phase was advanced.
- No exchange order placement, cancellation, modification, withdrawal or wallet signing was added.


## Verified MCP integer-boundary regression — 2026-11-11

- Code commit `ae93896350a0cd4128a7a919bf32cace61582522`; GitHub Actions run `42958954122`: **SUCCESS**.
- Actual CI job log: targeted Ruff passed; dashboard JavaScript syntax passed; pytest **565 passed, 2 warnings**.
- Five new parameterized cases passed: Boolean Spot kline limit, Boolean history timestamp, Boolean cross-chain decimals, Boolean aggregate-trade timestamp and Boolean research-snapshot timestamp. All assert rejection before the `_get` or `_post` call is made.
- The exact 565-pass count belongs to code/test commit `ae93896350a0cd4128a7a919bf32cace61582522`, not automatically to the later docs-only checkpoint.
- No phase acceptance status changed. Full audit remains INCOMPLETE because all 54 provider/service modules have not been completed line-by-line and the MCP local snapshot-persistence architecture decision remains open.


## Scanner Boolean numeric-response validation — 2026-11-11

### Confirmed defect and correction
- Direct source review found that both `backend/app/services/market_scanner.py` and `backend/app/services/futures_scanner.py` called `float(value)` without excluding Boolean inputs. In Python, Boolean values are numerically coercible; malformed upstream values such as `true` could therefore be accepted as numeric price/percentage/volume data.
- Both scanner `_number` helpers now return unavailable (`None`) for Boolean values before numeric conversion. Existing finite-number checks remain in place.
- Added Spot regression coverage for Boolean `lastPrice`, `priceChangePercent`, and `quoteVolume`; Futures coverage for the same USDⓈ-M fields plus the COIN-M `baseVolume` fallback path. Tests require the affected eligible market row to be counted as failed rather than included as a valid result.
- Code/test commit: `d2a51830fc09ccbd819ecbf000415cd5c2d4b56d`.

### Verification and gate
- CI for this commit must complete successfully before the correction is marked verified. No test count or CI pass is claimed at this point.
- This closes only the Boolean numeric-coercion defect in the two scanner parsers. It does not resolve per-symbol failure ledgers, all-contract/all-pair order-book depth, recent-average volume surge, market-cap enrichment, or other Phase 01 gaps.
- Provider/service inventory remains 54 source modules (excluding package initializer files); a complete line-by-line review of all modules and the full route surface remains incomplete. The MCP local snapshot-save architecture decision, type/security scanning, and live deployment/provider checks remain open.
- Pre-Coding Full Audit: INCOMPLETE. SPOT Phase 01: IN_PROGRESS. FUTURES Phase 01: IN_PROGRESS. Combined Phase 01: INCOMPLETE. Phase 02: LOCKED.
- No order execution or wallet capability was added.


## Verified scanner correction and aggregate-trade stream audit — 2026-11-11

### Scanner correction verification
- Code/test commit `d2a51830fc09ccbd819ecbf000415cd5c2d4b56d`; GitHub Actions run `42959434159`: **SUCCESS**.
- Actual job log confirms targeted Ruff passed, dashboard JavaScript syntax passed, and pytest **567 passed, 2 warnings**.
- The 567-pass count belongs only to commit `d2a51830fc09ccbd819ecbf000415cd5c2d4b56d`.

### Additional confirmed stream-normalization defect
- Review of `backend/app/services/aggregate_trade_stream.py` found `int()` accepted Boolean and fractional values for aggregate trade ID and event/trade timestamps; `float()` accepted Boolean price/quantity values. The normalizer also assumed the decoded payload was a dictionary before calling `.get()`.
- The normalizer now rejects non-object payloads, Boolean/fractional integer fields, negative IDs/timestamps, and Boolean price/quantity values before constructing a persisted row.
- Added regression tests covering all these invalid input classes.
- Code/test commit: `e7c907e061828c92ec2536d1011cae252b74ff74`. CI is pending and must be inspected before this fix is accepted as verified.

### Audit boundary
- This pass reviewed six additional service modules: advanced derivatives analysis, aggregate-trade stream, catalyst analysis, combined derivatives intelligence, cross-chain smart money and cross-chain token intelligence; and reviewed derivatives collector, ratio store, EVM transfer store and historical collector source sections. These inspections do not complete a line-by-line audit of the remaining service inventory.
- A further candidate review item is present in the derivatives ratio store timestamp parser: it calls `int(row["timestamp"])` without an explicit Boolean/fractional guard. This is not yet changed; confirm provider response contract and add regression tests before correction.
- Pre-Coding Full Audit remains INCOMPLETE. SPOT/FUTURES Phase 01 remain IN_PROGRESS; Combined Phase 01 INCOMPLETE; Phase 02 LOCKED. No order execution capability added.


## Aggregate-trade and market-history numeric boundary audit — 2026-11-11

### Aggregate-trade correction verified
- Commit `e7c907e061828c92ec2536d1011cae252b74ff74`; GitHub Actions run `42959561162`: **SUCCESS**. Targeted Ruff passed, dashboard JavaScript syntax passed, pytest **568 passed, 2 warnings**.
- The normalizer now rejects non-object payloads, Boolean/fractional IDs and timestamps, negative IDs/timestamps, and Boolean price/quantity fields. The 568-pass count belongs to this commit.

### Additional confirmed ingestion-boundary defects corrected (CI pending)
- `FundingRateStore`: `int(fundingTime)` accepted Boolean/fractional values; float conversion accepted Boolean funding-rate/mark-price values.
- `OpenInterestStore`: `int(timestamp)` accepted Boolean/fractional values; float conversion accepted Boolean OI/supply metrics.
- `HistoricalKlineStore`: timestamp/trade-count `int()` coercion accepted Boolean/fractional values; OHLCV float conversion accepted Boolean values.
- `normalize_force_order`: numeric conversion accepted Boolean price/quantity fields and timestamp `int()` accepted Boolean/fractional values; non-object payloads were not rejected before dictionary access.
- The above are now rejected before persistence/normalization. Regression tests cover Boolean and fractional integer fields plus Boolean float-like fields across these boundaries.
- Code/test commit: `4c9b1604f170ea1c5d5eaa097136f93851518117`. CI is pending; no pass is claimed yet.

### Remaining audit observations
- `DerivativesRatioStore._normalize` and `DerivativesSignalStore.save` also contain timestamp `int()` / integer-instance checks that warrant a focused follow-up for Boolean/fractional input rejection. These paths were not modified in this checkpoint.
- Full provider/service and route audit remains INCOMPLETE. Paired Spot/Futures Phase 01 remains IN_PROGRESS / IN_PROGRESS; combined Phase 01 INCOMPLETE; Phase 02 LOCKED.


## Verified market-history ingestion and derivatives snapshot follow-up — 2026-11-11

### Market-history and liquidation validation verified
- Code/test commit `4c9b1604f170ea1c5d5eaa097136f93851518117`; GitHub Actions run `42959727771`: **SUCCESS**. Targeted Ruff passed, dashboard JavaScript syntax passed, pytest **586 passed, 2 warnings**.
- This verifies strict non-Boolean integer timestamps for funding-rate and open-interest stores; strict integer kline timestamps/trade counts; rejection of Boolean float-like metrics; and stricter liquidation event parsing. The 586-pass count belongs to this commit.

### Derivatives ratio and signal snapshot follow-up (CI pending)
- `DerivativesRatioStore._normalize` now rejects Boolean/fractional timestamps instead of applying `int()` coercion.
- `DerivativesSignalStore.save` now requires a non-negative, non-Boolean integer end timestamp. Its history query validates integer/non-Boolean limit and optional time bounds.
- Added regression tests for Boolean/fractional/negative snapshot timestamps and Boolean/fractional ratio timestamps.
- Code/test commit: `2b0b8d33cbcf5b1a9a13be97808aa76e21b4b63d`; CI pending.

### Gate status
- Pre-Coding Full Audit remains INCOMPLETE. SPOT Phase 01 IN_PROGRESS; FUTURES Phase 01 IN_PROGRESS; Combined Phase 01 INCOMPLETE; Phase 02 LOCKED.


## Verified derivatives timestamp boundary correction — 2026-11-11

- Code/test commit `2b0b8d33cbcf5b1a9a13be97808aa76e21b4b63d`; GitHub Actions run `42959858424`: **SUCCESS**.
- Actual job log confirms targeted Ruff passed, dashboard JavaScript syntax passed, pytest **591 passed, 2 warnings**.
- The regression cases reject Boolean/fractional ratio timestamps and Boolean/fractional/negative snapshot end timestamps; history limit and optional timestamp bounds also reject Boolean/non-integer inputs.
- The 591-pass count belongs to the code/test commit only. Current docs HEAD `6a384ce460d5f524136fc43df389d2c360356fba` has a separate CI run; inspect it independently.
- Full audit remains INCOMPLETE. This correction does not advance paired Phase 01 acceptance or unlock Phase 02.


## Order-flow and data-quality input validation — 2026-11-11

### Order-flow correction verified
- Commit `40e37bb1a758cad86564310b46989f0f88de0881`; GitHub Actions run `42960326700`: **SUCCESS**. Actual job log confirms Ruff passed, dashboard JavaScript syntax passed, pytest **592 passed, 2 warnings**.
- `analyze_order_flow` now requires non-Boolean integer request boundaries; rejects Boolean threshold arguments; and counts malformed rows, Boolean/fractional trade timestamps, Boolean price/quantity/notional fields and non-object trade rows as rejected input rather than normalizing them into numeric data.

### Historical coverage and data-quality request controls (CI pending)
- `HistoricalCoverageEngine.inspect` now requires non-Boolean integer start/end timestamps; constructor safety limit must be a positive non-Boolean integer.
- `MarketDataQualityEngine.inspect` now requires integer lookback hours and a non-negative, non-Boolean integer optional clock override.
- Added regression tests for Boolean/fractional timestamps and Boolean/fractional/negative time controls.
- Code/test commit: `feccc885dde07c86eb0c531b30507dbeafadf2d9`. CI not yet available; no pass claimed.

### Remaining source review notes
- Direct review of liquidity behavior and sweep confirmation found additional unchecked numeric conversions (depth levels, event/trade timestamps and thresholds). Those paths remain open and require separate focused validation/tests; no claim of complete liquidity-analysis audit.
- The wider provider/service and FastAPI route audit remains incomplete. Phase 01 acceptance gates remain unchanged.


## Liquidity and historical data-quality audit checkpoint — 2026-11-11

### Historical coverage and quality request validation verified
- Commit `feccc885dde07c86eb0c531b30507dbeafadf2d9`; Actions run `42960402710`: **SUCCESS**, Ruff and dashboard JavaScript syntax passed, pytest **598 passed, 2 warnings**.
- Coverage start/end times and safety limits now require strict integer inputs; MarketDataQuality lookback and optional clock override reject Boolean/fractional/negative values.

### Liquidity behavior correction verified
- Commit `923369a5b2bb9a17a0a887b17f175e22788fb65a`; Actions run `42960545107`: **SUCCESS**, Ruff and dashboard JavaScript syntax passed, pytest **600 passed, 2 warnings**.
- Liquidity behavior now rejects malformed snapshot/trade rows, Boolean/fractional timestamps, Boolean numeric thresholds and Boolean depth/price/notional metrics; invalid rows are counted rather than coerced. Validated trade numeric values are normalized before aggregation.

### Liquidity sweep confirmation correction (CI pending)
- Candle open timestamps now require unique non-negative integer values; OHLC Boolean values are rejected; trade and nearest-context timestamps are accepted only as non-Boolean integers; request time windows and swing settings are validated.
- Added tests for Boolean/fractional candle and trade timestamps, Boolean OHLC, and invalid time controls.
- Commit `f43f4a6f81aa2cf2100c83f681d6d4bf8b851e9c`; CI queued/in progress. No pass claimed yet.

### Audit boundary
- These changes close only specific input-validation defects. The full service/provider line-by-line audit and route-level behavioral/security audit remain incomplete; no Phase 01 acceptance gate is being marked complete.


## Liquidity sweep and performance API boundary review — 2026-11-11

### Liquidity sweep correction verified
- Commit `f43f4a6f81aa2cf2100c83f681d6d4bf8b851e9c`; Actions run `42960668769`: **SUCCESS**, Ruff and dashboard JavaScript syntax passed, pytest **602 passed, 2 warnings**.
- Sweep confirmation now strictly validates candle timestamps and request windows, rejects Boolean OHLC, ignores malformed trade timestamps, and avoids integer truncation when pairing nearest timestamp context.

### Performance evaluator request-argument correction (CI pending)
- `MarketConfluencePerformance.evaluate` and `price_path` now require integer, non-Boolean `limit` and `hours` bounds.
- Regression tests added for Boolean and fractional request values.
- Commit `78b9831806e7dd084b226e5b7826e2b67919f371`; CI pending.
- This does not complete the broader historical performance service audit; its persisted timestamp and numeric assumptions still require continued review.


## Performance evaluator argument validation — verified CI evidence (2026-11-11)
- Code/test commit `78b9831806e7dd084b226e5b7826e2b67919f371`; Actions run `42960815725`: **SUCCESS**. Actual job log: targeted Ruff passed, dashboard JavaScript syntax passed, pytest **603 passed, 2 warnings**.
- `evaluate(limit=...)` and `price_path(hours=...)` reject Boolean/fractional bounds. This closes only those public request argument checks; deeper historical outcome parsing remains under review.


## Liquidation cluster request-boundary review — 2026-11-11
- `LiquidationClusterAnalysis.analyze` now requires non-Boolean integer start/end timestamps, limit, bucket width and minimum-event count. Boolean/fractional values are rejected before SQLite query execution.
- Regression tests cover Boolean/fractional time and numeric query controls.
- Code/test commit `f3bc28e1b37a896ddd4034440523f897b4d45c27`; CI pending at documentation checkpoint.
- This does not verify the truthfulness/completeness of the upstream liquidation snapshot stream; the collector still explicitly documents partial-feed limitations.


## RSS feed network-boundary correction — 2026-11-11

- Source review confirmed the RSS provider followed redirects and read each response body fully before parsing, with no byte ceiling. A configured HTTPS feed could therefore redirect to another destination, and a large feed response could consume unbounded memory before item-level truncation.
- Provider commit: `046bba3b253a99b70076a68344fe8d3a468291f6`; regression-test commit: `cf36eb8a1608bca207c9882ae0778a8560b951b3`.
- Redirect following is explicitly disabled on feed requests, including when a caller supplies an AsyncClient. Feed bodies are consumed incrementally and rejected once the configurable 1 MiB default limit is exceeded. Invalid size-limit configuration is rejected.
- Regression tests cover a redirect response, oversized streamed content, and invalid size-limit values. GitHub Actions run `42962156783` was queued at the time of this documentation entry; no CI pass is claimed until its completed job log is checked.
- This is a provider-level reliability/security correction only. It does not complete the full provider/service or route audit, nor does it change any paired-phase status.
- SPOT Phase 01: IN_PROGRESS; FUTURES Phase 01: IN_PROGRESS; Combined Phase 01: INCOMPLETE; Phase 02: LOCKED. No order execution or wallet capability was added.


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
