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
- Latest verified test checkpoint before the liquidation collector correction: `d560bd5bb803c25cec15b6d2d5756a1086bb8d28`; GitHub Actions run `42928650029` SUCCESS, 530 passed, 2 warnings.
- Liquidation event normalization now rejects malformed/non-finite quantity and price values and negative timestamps; regression tests are included in the 530-pass checkpoint.
- Ruff core rules and dashboard JavaScript syntax passed on that checkpoint. The Ruff CI target list has since been expanded to include the changed liquidation collector and its test; the expanded workflow is awaiting its own CI verification.
- Local working-tree status: UNVERIFIED through the remote GitHub interface.
- PR #1: OPEN / DRAFT; do not merge without explicit user approval.
- Main branch: unchanged.

## Continuity

Resume by completing the pre-coding audit gate, review current CI and static-analysis results, fix confirmed current-scope defects, and only then implement SPOT Phase 01. After SPOT Phase 01 acceptance, implement FUTURES Phase 01. Do not start Phase 02 until both Phase 01 statuses are COMPLETE.


## Latest audit additions — 2026-11-11

- Market-confluence snapshot storage now rejects Boolean/fractional timestamps and Boolean/non-finite/non-positive reference prices; regression tests added.
- EVM transfer indexer errors no longer return raw RPC/transport exception messages; token-bearing exception regression test added.
- Ruff core CI target list includes both updated storage modules and their tests; latest expanded-workflow CI verification must pass before treating this checkpoint as validated.
- These are existing-code validation/security fixes only; no new paired Phase 01 functionality has started.

- EVM index route now rejects Boolean/fractional JSON block numbers and chunk sizes before provider calls; route-level regression tests added.
- Prior Ruff-only CI failures were traced to a semicolon in the pre-existing snapshot test file newly brought into the targeted lint set; test formatting has been corrected. Latest full CI on the newest API-test/docs commit is pending.


### Verified latest code/test checkpoint

- Commit `6a19418c531913e83a93a55479c3ff3c0ca9d746`, CI run `42929655489`: **SUCCESS**.
- Ruff core checks: passed; dashboard JavaScript syntax: passed; pytest: **537 passed, 2 warnings**.
- This includes strict EVM block request validation, sanitized EVM indexer errors, and market-confluence numeric validation regressions.
- Later documentation-only commits still need CI confirmation on the latest HEAD.


### Audit continuation — 2026-11-11

- Latest HEAD `be448172169bbb68d00c827f496eaab82780c598`: CI run `42929783007` **SUCCESS**. Prior audit-doc checkpoint `16c8fb27eabfd7d5392578e34464ecc51929e3f4`: run `42929771515` **SUCCESS**. The exact 537-pass pytest count is tied to code/test checkpoint `6a19418c531913e83a93a55479c3ff3c0ca9d746`, not automatically attributed to later docs-only commits.
- MCP architecture audit: `save_market_confluence_snapshot` is an MCP tool that POSTs a descriptive local research snapshot. It does not execute trades or wallet actions, but it means MCP is not strictly read-only. Architecture decision remains OPEN; no change made without approval.
- Binance Spot/Futures REST provider adapters currently have no common retry/backoff or explicit Retry-After/rate-limit policy. Remains open for audit and Phase 01 coverage.
- MCP integer argument boundary review (Boolean-as-integer) remains pending framework-level validation tests.
- PR #1 OPEN / DRAFT / unmerged; main unchanged; 77 commits ahead / 0 behind.
- Pre-Coding Full Audit INCOMPLETE; SPOT Phase 01 IN_PROGRESS; FUTURES Phase 01 IN_PROGRESS; combined Phase 01 INCOMPLETE; Phase 02 LOCKED.


### Confirmed authentication fix — 2026-11-11

- Production auth previously allowed a weak AI-client key to match if a separate strong owner key satisfied the startup gate. Middleware now matches only client keys with length >=32; regression test checks weak-key 401 and strong owner-key success.
- Commits: `ffad59b3f906c49ffc539838a289357f18d3d548` (fix), `205c2fa2a36f72709748803c01de3e535c6b575e` (test). CI pending verification at time of ledger update.
- No Phase 01 feature work started; paired Phase 01 remains incomplete and Phase 02 locked.


### Authentication regression verification and API review — 2026-11-11

- Run `42931082393` (test checkpoint `205c2fa2a36f72709748803c01de3e535c6b575e`): SUCCESS; Ruff targeted checks passed; dashboard JS syntax passed; **538 pytest passed, 2 warnings**. Warnings are dependency deprecations.
- Docs HEAD `797f5c844bdf1f2f3343386418e76c3ed333cf95` run `42931109389`: SUCCESS. 538 test count belongs to the code/test checkpoint above.
- Enumerated 80 API route decorators; targeted review covered auth/error middleware, scanners/preflight, EVM indexing, confluence persistence, derivatives collection/history, and market-data history/quality. This is not yet a full line-by-line audit of all routes.
- Spot/Futures providers use 15-second defaults but no shared retry/backoff or explicit Retry-After handling. No live exchange connectivity test performed.
- Full audit remains INCOMPLETE. Spot Phase 01 and Futures Phase 01 remain IN_PROGRESS; Phase 02 LOCKED; no feature coding started.


### Order-book Futures sequence fix — 2026-11-11

- Fixed Futures first-event snapshot bridge: now accepts snapshot overlap (`U <= lastUpdateId <= u`) or direct continuation (`pu == lastUpdateId`); subsequent events require `pu == previous u`. Spot keeps its distinct `lastUpdateId + 1` bridge rule.
- Added strict integer validation for update IDs and regression cases for valid overlap/direct continuation, unbridged gap, malformed IDs, and Spot behavior. Legacy Futures fixture now includes `pu`.
- Final CI: run `42932203177` at `d4b4820d6c1d3a7c94716608fce00eaf55139cb9` **SUCCESS**; Ruff including order-book service/tests passed; dashboard JS passed; **548 passed, 2 warnings**. Earlier interim CI failures were resolved (old fixture lacked `pu`; lint found unused test import).
- No live stream test. Full audit remains INCOMPLETE; both Phase 01 tracks IN_PROGRESS; Phase 02 LOCKED; no Phase 01 feature coding started.


### Order-book reader queue shutdown fix — 2026-11-11

- Found and fixed a bounded-queue termination bug: when the order-book WebSocket reader exited while its queue was full, its close sentinel could be dropped silently and the consumer could wait forever after draining the queue.
- Reader shutdown now makes room for the sentinel by discarding one buffered delta, causing safe reconnect/resnapshot rather than continuing with potentially incomplete depth state.
- Added two async regression tests: full-queue socket termination and full-queue reader cancellation.
- Final CI run 42933491101 on 29db479fb82cdd9a90b86f81300d15f9b8dc234c: SUCCESS; Ruff and dashboard JS checks passed; 550 pytest passed, 2 warnings.
- Earlier CI attempts 42933359688 (missing test import) and 42933385702 (test did not consume expected cancellation) failed; both harness defects were fixed before final success.
- No live Binance WebSocket test. Full audit remains INCOMPLETE; Spot Phase 01 and Futures Phase 01 IN_PROGRESS; combined Phase 01 INCOMPLETE; Phase 02 LOCKED; no Phase 01 feature coding started.


### Order-book REST snapshot sequence-ID validation — 2026-11-11

- Removed permissive int() coercion of REST snapshot lastUpdateId. The collector now rejects Boolean, fractional, and string IDs instead of truncating/coercing them into valid-looking sequence values.
- Added regression tests for malformed and valid snapshot IDs.
- CI run 42933697618 at 716709c26781b52300dc77188161196962a268a5: SUCCESS; Ruff and dashboard JS checks passed; 554 pytest passed, 2 warnings.
- No live exchange connectivity test. Full audit remains INCOMPLETE; both Phase 01 tracks IN_PROGRESS; Phase 02 LOCKED; no Phase 01 feature coding started.


### Session resume verification — 2026-11-11

- Work branch HEAD before this documentation checkpoint: `21484ddb0bf4a4c7c6ec83279930546b4535405b`.
- PR #1: OPEN / DRAFT / unmerged; branch comparison 104 ahead / 0 behind main; main unchanged.
- Latest CI run on that HEAD: `42933836840` SUCCESS; targeted Ruff `E4,E7,E9,F` passed; dashboard JavaScript syntax passed; pytest **554 passed, 2 warnings**.
- Current session inspected both Binance provider adapters, both scanner services, their scanner tests and the CI workflow; inventoried 80 API route decorators and 54 provider/service files. Full line-by-line audit of all routes/services is not complete.
- Pre-Coding Full Audit remains **INCOMPLETE**. Provider retry/Retry-After handling, MCP snapshot-save architecture acceptance, live deployment/Binance connectivity, type/security scanning and local working-tree status remain unresolved/unverified.
- SPOT Phase 01: **IN_PROGRESS**; FUTURES Phase 01: **IN_PROGRESS**; Combined Phase 01: **INCOMPLETE**; Phase 02: **LOCKED**.
- No Phase 01 feature implementation was changed in this checkpoint because the mandatory pre-coding audit gate remains open. Resume by completing that gate; then start with SPOT Phase 01 only.


### Provider retry/backoff correction — 2026-11-11

- Commit `4ecf7805578df40b6d80628144e100b454ace044`: added shared bounded GET retry helper and integrated it into the separate Spot and Futures REST adapters.
- HTTP 429 honours numeric/HTTP-date `Retry-After`; missing/invalid header uses exponential fallback; transport/5xx retry is bounded; HTTP 418 is not retried.
- Added tests for 429, 418, 503, transport failure, fallback backoff and HTTP-date parsing; expanded Ruff targets for both adapters and new tests.
- CI run `42957685379` was **IN_PROGRESS** at documentation time. No pass is claimed pending final run/job-log verification.
- No live Binance rate-limit test; per-symbol/per-contract retry failure evidence remains outstanding.
- Pre-Coding Full Audit remains **INCOMPLETE**; SPOT/FUTURES Phase 01 remain **IN_PROGRESS**; Combined Phase 01 **INCOMPLETE**; Phase 02 **LOCKED**.


### Verified provider retry/backoff CI — 2026-11-11

- Code/test commit `4ecf7805578df40b6d80628144e100b454ace044`; GitHub Actions run `42957685379`: **SUCCESS**.
- Ruff targeted checks passed; dashboard JavaScript syntax passed; pytest **560 passed, 2 warnings**.
- The 560-pass count belongs to the code/test commit above. The later documentation-only HEAD `6d3db66cb0a00f9f0f1f83776d18536b335cc857` has not been assigned that test count.
- No live Binance 429/418 test. Pre-Coding Full Audit remains **INCOMPLETE**; SPOT Phase 01 and FUTURES Phase 01 remain **IN_PROGRESS**; combined Phase 01 **INCOMPLETE**; Phase 02 **LOCKED**.


### MCP Boolean-as-integer boundary correction — 2026-11-11

- Commit `ae93896350a0cd4128a7a919bf32cace61582522`: added a type-hint-driven guard to all 38 MCP tools, rejecting Boolean values for integer and optional-integer parameters before tool logic/API calls.
- Added parameterized regression cases for Spot kline limit, history timestamp, cross-chain decimals, aggregate-trade timestamp and research snapshot timestamp. Tests assert no API call is made.
- API route inventory: 80 route decorators. MCP exposes one local research snapshot POST; no Binance trading/order endpoint was identified in the reviewed MCP/API surface. This does not mean MCP is strictly read-only for local storage.
- CI run `42958954122` was IN_PROGRESS at documentation time; no test pass is claimed pending completed job-log review.
- Pre-Coding Full Audit remains INCOMPLETE: full line-by-line review of all 54 provider/service modules and MCP snapshot persistence architecture decision remain open.
- SPOT Phase 01: IN_PROGRESS; FUTURES Phase 01: IN_PROGRESS; Combined Phase 01: INCOMPLETE; Phase 02: LOCKED.


### MCP integer-boundary CI verification — 2026-11-11

- Code/test commit `ae93896350a0cd4128a7a919bf32cace61582522`; GitHub Actions run `42958954122`: **SUCCESS**.
- Targeted Ruff passed; dashboard JavaScript syntax passed; pytest **565 passed, 2 warnings**. Five Boolean-as-integer boundary regression cases passed.
- Exact count belongs to the code/test commit above; subsequent docs-only HEAD is a separate commit.
- Pre-Coding Full Audit remains INCOMPLETE; SPOT/FUTURES Phase 01 remain IN_PROGRESS; Combined Phase 01 INCOMPLETE; Phase 02 LOCKED.


### Phase 01 scanner Boolean numeric-response correction — 2026-11-11

- Confirmed and fixed Boolean-to-number coercion in the Spot and Futures scanner numeric parsers. Boolean ticker values are now treated as invalid/missing data, not numeric prices, percentages or volumes.
- Added regression cases for Spot ticker numeric fields, USDⓈ-M Futures ticker numeric fields, and the COIN-M base-volume-derived notional fallback.
- Code/test commit: `d2a51830fc09ccbd819ecbf000415cd5c2d4b56d`.
- CI verification is pending; do not mark this fix CI-verified until the actual run and job log are checked.
- Phase status unchanged: SPOT Phase 01 IN_PROGRESS; FUTURES Phase 01 IN_PROGRESS; Combined Phase 01 INCOMPLETE; Phase 02 LOCKED.
- Full pre-coding audit remains INCOMPLETE; remaining scanner acceptance criteria are unchanged.


### Scanner and aggregate-trade data-integrity checkpoint — 2026-11-11

- Scanner Boolean numeric correction: commit `d2a51830fc09ccbd819ecbf000415cd5c2d4b56d`; CI run `42959434159` **SUCCESS**, Ruff passed, dashboard JS passed, pytest **567 passed, 2 warnings**.
- Aggregate-trade normalizer hardening: commit `e7c907e061828c92ec2536d1011cae252b74ff74`; CI pending. The normalizer rejects malformed non-object payloads, Boolean/fractional integer IDs/timestamps, negative IDs/timestamps, and Boolean price/quantity fields.
- Paired phase status unchanged: SPOT Phase 01 IN_PROGRESS; FUTURES Phase 01 IN_PROGRESS; Combined Phase 01 INCOMPLETE; Phase 02 LOCKED.
- Full pre-coding audit remains INCOMPLETE.


### Aggregate-trade and market-history validation checkpoint — 2026-11-11

- Aggregate-trade normalization fix `e7c907e061828c92ec2536d1011cae252b74ff74`: CI run `42959561162` **SUCCESS**, Ruff passed, dashboard JS passed, pytest **568 passed, 2 warnings**.
- Funding-rate, open-interest, historical-kline and liquidation ingestion validation hardening committed as `4c9b1604f170ea1c5d5eaa097136f93851518117`; CI pending.
- No phase acceptance criteria are marked complete by these data-integrity fixes. SPOT Phase 01 IN_PROGRESS; FUTURES Phase 01 IN_PROGRESS; Combined Phase 01 INCOMPLETE; Phase 02 LOCKED.


### Market-history and derivatives timestamp integrity checkpoint — 2026-11-11

- Funding/OI/kline/liquidation numeric validation commit `4c9b1604f170ea1c5d5eaa097136f93851518117`: CI run `42959727771` **SUCCESS**, Ruff and dashboard JS passed, pytest **586 passed, 2 warnings**.
- Derivatives ratio and signal-snapshot timestamp validation commit `2b0b8d33cbcf5b1a9a13be97808aa76e21b4b63d`: CI pending.
- Paired phase statuses remain SPOT Phase 01 IN_PROGRESS; FUTURES Phase 01 IN_PROGRESS; Combined Phase 01 INCOMPLETE; Phase 02 LOCKED.


### Verified derivatives timestamp validation — 2026-11-11

- Code/test commit `2b0b8d33cbcf5b1a9a13be97808aa76e21b4b63d`; CI run `42959858424` **SUCCESS**, Ruff and dashboard JS passed, pytest **591 passed, 2 warnings**.
- This is a data-integrity correction only. SPOT Phase 01 IN_PROGRESS; FUTURES Phase 01 IN_PROGRESS; Combined Phase 01 INCOMPLETE; Phase 02 LOCKED.


### Order-flow and time-boundary validation checkpoint — 2026-11-11

- Order-flow strict numeric validation commit `40e37bb1a758cad86564310b46989f0f88de0881`: CI run `42960326700` **SUCCESS**, Ruff and dashboard JS passed, pytest **592 passed, 2 warnings**.
- Historical coverage and market-data-quality request validation commit `feccc885dde07c86eb0c531b30507dbeafadf2d9`: CI pending.
- Additional liquidity behavior/sweep numeric-boundary review remains open.
- Paired phase status unchanged: SPOT Phase 01 IN_PROGRESS; FUTURES Phase 01 IN_PROGRESS; Combined Phase 01 INCOMPLETE; Phase 02 LOCKED.


### Historical coverage and liquidity validation checkpoint — 2026-11-11

- Historical coverage / market-data-quality argument validation commit `feccc885dde07c86eb0c531b30507dbeafadf2d9`: CI **SUCCESS**, pytest **598 passed, 2 warnings**.
- Liquidity behavior strict input validation commit `923369a5b2bb9a17a0a887b17f175e22788fb65a`: CI **SUCCESS**, pytest **600 passed, 2 warnings**.
- Liquidity sweep confirmation timestamp/numeric validation commit `f43f4a6f81aa2cf2100c83f681d6d4bf8b851e9c`: CI pending at checkpoint.
- SPOT Phase 01 IN_PROGRESS; FUTURES Phase 01 IN_PROGRESS; Combined Phase 01 INCOMPLETE; Phase 02 LOCKED.


### Liquidity sweep and performance argument checkpoint — 2026-11-11

- Liquidity sweep confirmation correction commit `f43f4a6f81aa2cf2100c83f681d6d4bf8b851e9c`: CI **SUCCESS**, pytest **602 passed, 2 warnings**.
- Market confluence performance strict limit/hour argument validation commit `78b9831806e7dd084b226e5b7826e2b67919f371`: CI pending.
- Paired phase remains SPOT Phase 01 IN_PROGRESS; FUTURES Phase 01 IN_PROGRESS; Combined Phase 01 INCOMPLETE; Phase 02 LOCKED.


### Performance evaluator request validation — verified 2026-11-11

- Commit `78b9831806e7dd084b226e5b7826e2b67919f371`: CI run `42960815725` **SUCCESS**, Ruff and dashboard JS passed, pytest **603 passed, 2 warnings**.
- Phase status unchanged: SPOT Phase 01 IN_PROGRESS; FUTURES Phase 01 IN_PROGRESS; Combined Phase 01 INCOMPLETE; Phase 02 LOCKED.


### Liquidation cluster query validation — 2026-11-11

- Added strict non-Boolean integer validation for liquidation cluster time bounds, limit, bucket width and minimum event count. Commit `f3bc28e1b37a896ddd4034440523f897b4d45c27`; CI pending.
- Phase status unchanged: SPOT Phase 01 IN_PROGRESS; FUTURES Phase 01 IN_PROGRESS; Combined Phase 01 INCOMPLETE; Phase 02 LOCKED.


## Provider audit note — 2026-11-11

RSS provider redirect following is disabled and streamed feed responses are capped at 1 MiB by default. Tests cover redirect, oversize and invalid limit cases. Code/test commits: `046bba3b253a99b70076a68344fe8d3a468291f6`, `cf36eb8a1608bca207c9882ae0778a8560b951b3`. CI run `42962156783` pending verification at this checkpoint. Paired Phase 01 remains INCOMPLETE; Phase 02 remains LOCKED.
