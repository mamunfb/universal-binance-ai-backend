# Master Prompt 01 (SPOT) + Master Prompt 02 (FUTURES) — Repository Gap Audit

Audit basis:
- Repository: \`mamunfb/universal-binance-ai-backend\`
- Baseline branch: \`main\`, commit \`dfef59340c08fd20ba858efb78016ff8ff4e3997\`
- Spot prompt: \`master-prompts/MASTER_PROMPT_01_SPOT.md\`
- Futures prompt: canonical user-uploaded \`universal_crypto_master_prompt_futures.md\`, copied verbatim to \`master-prompts/MASTER_PROMPT_02_FUTURES.md\` on this branch
- Review method: static review of repository tree, README, API routes, providers, analysis services, readiness map, and selected tests. This document is not a claim that all tests or live endpoints were executed.

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
