# Project Progress Ledger
Last updated: 2026-11-20 — USDⓈ-M diagnostics and audit documentation committed; CI and Staging verification pending
Repository: `mamunfb/universal-binance-ai-backend`
Governing policy: [PROJECT_EXECUTION_GOVERNANCE.md](PROJECT_EXECUTION_GOVERNANCE.md)

## How to read this ledger

This is the active engineering progress source of truth. It tracks work packages, not paired SPOT/FUTURES development phases. The old paired phase statuses are historical and must not be mechanically converted into package completion.

Statuses: `UNASSESSED`, `NOT_STARTED`, `IN_PROGRESS`, `BLOCKED`, `VERIFICATION`, `COMPLETED`, `REOPENED`.

**Initial migration rule:** until current code, branch, PR and CI evidence are reconciled against each package, its status remains `UNASSESSED`. An old “Phase 01 IN_PROGRESS” entry is not sufficient evidence to assign a new package status.

## Work package register

| ID | Work package | Status | Evidence / next action |
|---|---|---|---|
| WP-00 | Baseline repository audit and migration | COMPLETED | Branch lineage, PR state, current CI evidence, historical audit records and package-level follow-up gates reconciled in the checkpoint below |
| WP-01 | CI/CD and build reliability | UNASSESSED | Verify latest workflows, runner execution, build reproducibility and billing/runner blockers |
| WP-02 | Backend architecture and API foundations | UNASSESSED | Map current architecture/contracts; inspect only current relevant evidence |
| WP-03 | Database, persistence and data integrity | UNASSESSED | Reconcile schemas, persistence, migrations, idempotency and recovery evidence |
| WP-04 | Binance Spot research capabilities | UNASSESSED | Map implementation against the Spot prompt without changing its analytical sequence |
| WP-05 | Binance Futures research capabilities | UNASSESSED | Map USDⓈ-M and COIN-M separately against the Futures prompt |
| WP-06 | Market-data infrastructure | UNASSESSED | Review source coverage, rate limits, timestamps, freshness and failure accounting |
| WP-07 | News, on-chain, tokenomics and AI research intelligence | UNASSESSED | Map provider coverage, verification, provenance and limitations |
| WP-08 | Risk, safety and research guardrails | UNASSESSED | Verify market separation, uncertainty, risk calculations and research-only boundaries |
| WP-09 | Frontend and institutional dashboard | IN_PROGRESS | Latest combined CI #1970: 687 passed; frontend 119, standalone Chromium 20, and performance evidence also verified; live integration and physical-device/assistive-technology gates remain open |
| WP-10 | Authentication and application security | UNASSESSED | Verify current auth, secrets handling, dependency/security checks |
| WP-11 | Cross-system integration | UNASSESSED | Review REST, dashboard, MCP and AI-client contracts |
| WP-12 | Full QA and performance | UNASSESSED | Separate local/mock evidence from live/staging/device evidence |
| WP-13 | Staging deployment and verification | UNASSESSED | Verify actual staging resources and smoke-test evidence; do not infer from a URL alone |
| WP-14 | Production readiness and deployment | UNASSESSED | Assess readiness only; production action requires explicit approval |

## Active task

- Active package: **WP-09 — Frontend and institutional dashboard**
- Status: **IN_PROGRESS**
- Reason: automated frontend, browser, performance and combined backend/dashboard checks now have current runner evidence; live cross-origin integration and physical-device/manual assistive-technology evidence remain outstanding.
- Next action: resolve the approved live integration prerequisites (exact HTTPS dashboard preview URL, backend URL, and an appropriately scoped QA credential) without changing production secrets/CORS or using a broadly privileged key; then complete physical-device and manual assistive-technology checks when a real device is available.
- WP-00 baseline reconciliation is completed. Do not reopen it unless a concrete discrepancy or regression is found.


## Completion evidence record template

Copy this block into a package section or append a dated record whenever a package changes status:

```text
Date:
Package ID / title:
Previous status -> new status:
Scope and acceptance criteria:
Branch:
Base commit:
Resulting commit SHA:
Changed files/components:
Tests/checks run (exact commands):
Test/CI run IDs and job results:
Runtime/browser/provider environment:
Coverage and missing-data accounting:
Confirmed defects fixed:
Known risks / limitations:
Blocked items and exact resolution:
Review decision:
Reopened package/dependents (if any) and reason:
```

## Historical references

- Former paired phase ledger: [PAIRED_PHASE_LEDGER.md](PAIRED_PHASE_LEDGER.md) — retired; retained as a pointer/history marker.
- Historical implementation findings and dated test records: [MASTER_PROMPT_IMPLEMENTATION_AUDIT.md](MASTER_PROMPT_IMPLEMENTATION_AUDIT.md). Historical phase locks in that file are not active workflow rules.
- Historical complete scope: [UNIVERSAL_PROJECT_SCOPE_AND_EXECUTION_CONTROL.md](UNIVERSAL_PROJECT_SCOPE_AND_EXECUTION_CONTROL.md), with the governance-precedence notice at its top.

## Last verified checkpoint — WP-09 handoff

**Verification date:** 2026-11-19  
**Repository:** `mamunfb/universal-binance-ai-backend`  
**Default branch:** `main`; observed HEAD `0e3b921ab83e18d4999c1eac87f45285a0f27b26`  
**Active branch:** `feat/institutional-dashboard-task-governance`  
**Base dashboard source:** `e9d89e2014c5298093a3c9b88f6727657663c21f`  
**Latest combined-suite commit at this checkpoint:** `23afefd7445ff0a6ecb62d58ed7bf7be0b96d4c9`  
**Working-tree visibility:** unavailable through the GitHub repository connector; no claim is made about uncommitted local changes.

### WP-00 completion evidence

- Reconciled the dashboard feature branch, old paired-phase audit branch, governance source branch, default branch, open PR #1, current workflow runs and the prior Dashboard QA audit.
- Created this continuation branch from the dashboard feature branch's verified HEAD. Compared with that base, it contains 16 commits and 15 changed files: governance docs/prompts, README links, five workflow branch-filter/condition changes and one test-only fixture correction. No `dashboard/**` runtime files or `backend/app/**` runtime source files changed.
- SPOT prompt's analytical body was verified unchanged against the dashboard base; both canonical market prompts contain 20 analytical phases. FUTURES prompt and resume/governance documents were added where absent.
- The old paired-phase ledger is now a retirement pointer. Historical lock instructions remain only in records with superseding notices.
- The separate source branch `docs/task-based-governance-v2` remains 237 commits ahead and 3 behind `main`; it is not a docs-only branch and must not be merged as a governance-only change. Existing PR #1 remains open/draft on the old branch and was not modified or merged.
- WP-00 is COMPLETED; its historical evidence is retained above and in the project audit files.

### WP-09 verified evidence

- Combined Backend + Dashboard CI Run #1969 / `44443701895`, commit `750b2c64ded70b3504e2cb51206fb7022837d457`: **success, 687 passed in 11.89s**. Dashboard HTML/script checks and JS syntax passed. The standalone Python-only step was skipped because the combined feature-branch step ran the full suite.
- Dashboard frontend Run `44443339378`: **119 tests passed** (110 contract + 9 accessibility), chart fixtures and JS syntax passed.
- Standalone Chromium browser Run `44443343939`: **20 passed, 0 failed, 0 skipped**.
- Performance Run `44443349312`, commit `1ef19349364abd0cedad7b4044c5fb1bfee2ab56`: successful. Lighthouse mobile Performance scores 100/99/100; FCP 904/1363/905 ms; LCP 1504/1705/1505 ms; TBT 0 ms; CLS 0.0000238/0/0.0000238. CPU/heap fixture details and artifact ID `14492516424` are recorded in `DASHBOARD_QA_AUDIT.md`.
- Backend run `44443399825` initially failed with 686 passed and one stale-date fixture failure. The test-only correction is in commit `750b2c64...`; the subsequent complete suite passed 687 tests. No backend runtime source was changed.
- Live integration Run `44443354893` completed its configuration check, but the live Chromium job was skipped because `DASHBOARD_PREVIEW_URL` and `RENDER_BACKEND_URL` were missing. The QA credential prerequisite also remains unconfigured. Do not call this live integration success.
- Physical-device testing, manual TalkBack/VoiceOver, production performance and long-session memory-leak evidence remain unverified. The Lighthouse/CPU/heap tests use a local static server and mocked data.

- Combined Backend + Dashboard CI Run #1970 / `44443985260`, commit `0797881c14d02d46ca958298265faf644766a711`: **success, 687 passed in 13.60s**. The actual runner log confirms Playwright Chromium installation, dashboard HTML validation (2 local script references), `node --check` for `dashboard/app.js`, `dashboard/chart.js` and `tests/dashboard_live_integration.cjs`, followed by the complete `python -m pytest -q` suite. The standalone Python-only step was skipped because the combined step ran the full suite. No runtime source changes were made in this evidence-only checkpoint.

- Combined Backend + Dashboard CI Run #1971 / `44444904102`, commit `23afefd7445ff0a6ecb62d58ed7bf7be0b96d4c9`: **success, 687 passed in 10.80s**. Actual runner logs confirm Playwright Chromium installation, dashboard HTML validation (2 script references), syntax checks for `dashboard/app.js`, `dashboard/chart.js`, and `tests/dashboard_live_integration.cjs`, and full Python test suite.
- Live Integration Run #1972 / `44444903951` completed its URL-configuration-check job successfully, but the live Chromium job was **skipped** because repository variables `DASHBOARD_PREVIEW_URL` and `RENDER_BACKEND_URL` are not configured. The updated live test no longer needs a bearer secret for its negative-auth/CORS smoke check, but still requires both URLs. Positive authenticated success remains intentionally untested until a least-privilege QA credential is designed.

### Other known package findings

- WP-01 remains UNASSESSED. Dashboard workflows are now wired to this branch, but a complete CI/CD architecture audit has not been performed.
- WP-06 remains UNASSESSED. Latest scheduled scan Run `44436848791` on `main` failed with Binance Spot HTTP 451 and Futures upstream-unavailable responses. This is an upstream access blocker for that run, not proof of an internal scanner defect; do not bypass legal/geographic restrictions.
- WP-13 remains UNASSESSED. Live staging integration is not verified because exact preview/backend URLs and QA credential are not configured.
- WP-14 remains UNASSESSED. Production readiness/deployment has not been authorized or performed.
- All other packages remain UNASSESSED until their own evidence is reconciled.

### Next exact action

1. Continue WP-09 by supplying/confirming exact staging dashboard and backend URLs for the secretless CORS/invalid-token smoke test; do not create/change repository variables, secrets, Render settings or CORS without explicit authorization. Positive authenticated success remains blocked on a least-privilege QA credential.
2. Complete physical-device responsive/keyboard testing and manual assistive-technology checks when a real device and tester are available.
3. Preserve the distinction between local/mock QA evidence and live/staging/production evidence.
4. Reopen WP-00 only if a concrete branch, PR, CI or baseline discrepancy is discovered.



## USDⓈ-M preflight diagnostics — 2026-11-20

**Scope:** WP-05 / WP-06 diagnostic hardening on `feat/institutional-dashboard-task-governance`. This is an in-progress investigation, not a completed market-data fix.

- Verified the provider's public USDⓈ-M exchange-info request uses `https://fapi.binance.com/fapi/v1/exchangeInfo`. Binance's current official USDⓈ-M Market Data documentation lists the same GET endpoint and request weight 1.
- Confirmed the previous provider called `response.raise_for_status()` but did not preserve the resulting HTTP status, bounded response body, retry-after, or safe rate-limit header. The preflight probe returned only the exception class.
- Added bounded diagnostics to caught `httpx.HTTPStatusError`: HTTP status, URL without query parameters, whitespace-normalized response body capped at 512 characters, `Retry-After`, and allow-listed `X-MBX-USED-WEIGHT-1M`. Cookie and arbitrary headers are not exposed.
- Added preflight failure categories for HTTP response errors, network timeouts, connection/protocol errors, and otherwise unclassified provider failures. No raw exception message or credentials are returned.
- No automatic retry was added. Statuses such as 418/429/451 must first be observed and handled according to their actual semantics; blindly retrying or routing around access restrictions would be unsafe.
- Regression tests added for HTTP 403, 418, 429, 451, 500, 503 and response-body truncation. The tests are committed but **have not yet been executed in a confirmed CI runner**.
- Workflow path filters now include `backend/app/providers/binance_futures.py` and `tests/test_binance_futures_provider.py`, so future provider changes are included in the Dashboard/Backend QA workflow.
- Commits: provider diagnostics `6f8eafc95ce09cfbbea378878a384591b680db61`; preflight classification `e0324f79a902c652ff5bec6dfa4b525dbb75c1e1`; initial tests `7d026e8470f5dae2f6fa66ddcaf0927eaf7fc0fe`; test harness correction `5fd593cb01189d3957026ed0865a0527f3d5318a`; workflow coverage `8956b8167b5a057a5492c4fed591d7d15f0176e6`.
- Render Staging remains deployed at commit `6fff1228936d3d507c2dc130f71d329946c42095`; auto-deploy is disabled. No Staging deploy was triggered, and no Production resource was changed.
- Render application logs show successful health and preflight HTTP requests, but no upstream USDⓈ-M error body/status was logged. Therefore the original Render-side root cause remains **unconfirmed**.
- Code/workflow checkpoint: `8956b8167b5a057a5492c4fed591d7d15f0176e6`. Documentation commits: `5c8565d375f63a4a7785f63c712631a181a298a1` and `79ec669c9b67ce33325793f717f3014de3613c00`. Current branch HEAD: `79ec669c9b67ce33325793f717f3014de3613c00`. The branch is seven commits ahead of the Staging baseline `6fff122`; changes affect provider diagnostics, preflight reporting, regression tests, workflow path filters, and audit documentation only.
- Local execution was unavailable because the execution container could not resolve GitHub to retrieve the repository. No local test pass is claimed.

### Next gates

1. Obtain a confirmed CI run on the current branch and inspect the actual runner logs, including the new provider tests.
2. After CI passes, deploy the exact feature-branch commit to the existing Staging service only when explicitly authorized; Render auto-deploy is disabled.
3. Re-run authenticated Staging preflight using the already configured least-privilege QA access, without exposing or changing the token.
4. Record the real USDⓈ-M HTTP status/body and determine whether the failure is Binance response policy, regional/network transport, timeout, or another provider condition.
5. Do not mark WP-05/WP-06 complete until real Staging evidence and the broader market-data audit gates are satisfied.
