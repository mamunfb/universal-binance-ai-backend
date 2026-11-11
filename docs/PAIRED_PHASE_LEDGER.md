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
