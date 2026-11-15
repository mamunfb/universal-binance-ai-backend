# Dashboard QA & Implementation Audit

**Date:** 2026-11-15  
**Working branch:** `feat/institutional-dashboard-design`  
**Audited source commit:** `3fab6c7a7f4d47bffa8981c71a7366789dec8256`  
**Scope:** dashboard CI, responsive layout, keyboard accessibility, JavaScript/API handling, rendering performance.  
**Change-control boundary:** `main`, PR merge state, and production deployment are intentionally unchanged.

## Executive status

This is a source and staging audit, not a release-readiness sign-off. The current staging URL serves a different, older dashboard implementation from the feature-branch source. Consequently, the staging browser observations below cannot be used as runtime verification of the feature branch.

| Area | Current evidence | Status |
|---|---|---|
| GitHub Actions runner | Workflow definition read back; no verified job/step log for audited feature-branch commit | **Not verified** |
| Feature-branch mobile layout | CSS source contains breakpoints at 1100px, 760px, 480px and 360px; no live render of this branch | **Source reviewed; runtime pending** |
| Feature-branch keyboard navigation | Mobile sidebar focus trap and Escape handling exist in `dashboard/app.js` at audited commit | **Source reviewed; runtime regression pending** |
| JavaScript/API errors | API wrapper has timeout, caller-abort handling, JSON-shape/error handling, sanitized backend details and network error messaging | **Source reviewed; runtime pending** |
| Rendering performance | Scanner search text uses per-table WeakMap caching; chart rendering caps displayed candles to the latest 120 | **Source reviewed; profiling pending** |
| Browser QA on staging | Visual viewport assessment at 360, 390, 768 and 1280 CSS-pixel widths | **Staging-only; not feature branch** |

## 1. CI runner verification

The branch workflow `.github/workflows/tests.yml` was read back at blob `8b93f937bda5008481455c0868981bfd317af8e0`.

Configured workflow:
- Push trigger for `main` and `feat/institutional-dashboard-design`.
- Pull-request trigger targeting `main`.
- Ubuntu latest runner, Python 3.12 and Node.js 22.
- Toolchain version output.
- Editable installation of `.[dev,mcp]`.
- Dashboard HTML/script-reference validation.
- `node --check` for `dashboard/app.js` and `dashboard/chart.js`.
- `python -m pytest -q`.

The available commit-workflow lookup returned an empty list, but that connector endpoint is documented as filtering to pull-request-triggered runs only. Therefore this result does **not** establish whether the push-triggered run executed. No runner job ID, completed step list, or log has been verified for the audited commit. Do not mark CI PASS or FAIL until the actual Actions run and its job logs are inspected.

## 2. Staging browser assessment

**URL:** https://universal-binance-ai-backend-aylm.onrender.com/dashboard/  
**Browser run:** https://agent.tinyfish.ai/runs/4eac2eac-d560-45a6-8b90-0314cd275e3a  
**Observed title:** `Binance AI Research`  
**Observed H1:** `Binance AI Market Research`

The staging page displayed an older single-page dashboard with configuration, readiness, scanner, evidence, snapshots, outcomes, price chart, data quality and raw-response panels. It did not contain the feature branch's Universal Binance AI sidebar, mobile-menu button or navigation structure.

At 360px, 390px, 768px and 1280px, the browser operator visually reported no horizontal scrollbar or clipped controls. This is a visual observation only: exact `scrollWidth/clientWidth` values were not available. The browser session could not inspect DevTools Console or Network panels. No state-changing buttons were clicked.

Because the staging deployment is not proven to contain the audited branch, these results are **not** a feature-branch acceptance test.

## 3. Responsive and keyboard accessibility source review

Feature-branch `dashboard/app.css` includes responsive rules for:
- 1100px: compact sidebar and controls.
- 760px: off-canvas sidebar and stacked/mobile controls.
- 480px: narrow pager and two-column control adjustments.
- 360px: narrow header and action wrapping.
- Reduced-motion preference.
- Visible focus styles for navigation, buttons, inputs, selects, pager controls and table scroll regions.

Feature-branch `dashboard/app.js` includes:
- Mobile sidebar open/close state and `aria-expanded` / `aria-label` updates.
- `inert` on the closed mobile sidebar.
- Focus moved into the sidebar on open and returned to the menu button on close.
- Escape closes the open sidebar.
- Tab and Shift+Tab wrap focus within the open mobile sidebar.

These are source-readback findings only. A real browser test against the feature-branch build remains required, including menu open/close, first/last focus wrapping, Escape, focus restoration, desktop breakpoint behavior and keyboard navigation across all pages.

## 4. JavaScript and API error handling source review

The API helper in `dashboard/app.js`:
- Requires a configured backend base URL.
- Rejects invalid/non-positive timeout values.
- Uses `AbortController` for timeout and caller cancellation.
- Sends `credentials: "omit"` and `cache: "no-store"`.
- Handles non-JSON responses, empty JSON responses and non-2xx responses.
- Sanitizes control characters and truncates backend-provided error details.
- Distinguishes timeout, cancellation, abort and network connection errors.

Health, scanner and chart paths also validate response object/array shapes and retain prior display data on several incomplete/invalid-response paths. No authenticated API requests were made during this audit. Runtime tests for 401/403, 404, 429, 5xx, timeout, abort, malformed JSON, empty body, invalid payload, offline mode and stale-request races remain outstanding.

## 5. Rendering and performance source review

Observed safeguards:
- Scanner search text is cached per row object in a `WeakMap`.
- Chart source processing is bounded by `MAX_SOURCE_CANDLES` and visible price candles are sliced to the latest 120.
- SVG elements are built through DOM APIs rather than injecting API data as HTML.
- Request sequence counters and abort controllers are used to prevent stale requests from replacing newer results.

No Lighthouse run, Performance trace, memory profile, large-market dataset benchmark or mobile-device profiling was performed. No performance improvement is claimed from source inspection alone.

## 6. Outstanding acceptance checks

1. Obtain a genuine CI run for the audited branch commit and inspect every job step and log.
2. Serve/build the feature-branch dashboard in an isolated QA environment without changing production.
3. Measure actual viewport dimensions and document `scrollWidth/clientWidth` at 360, 390, 480, 760, 768, 1100 and 1280px.
4. Run keyboard regression on the feature-branch mobile sidebar and all page controls.
5. Capture browser console errors and failed network requests.
6. Exercise API error cases with a controlled mock backend.
7. Profile initial render, scanner table rendering, chart rendering and memory under representative data volume.
8. Update this report with evidence, exact run IDs, logs and measured results.

## Change-control confirmation

No changes were made to `main`. No PR was merged, no production deployment was initiated, and no staging deployment was initiated during this audit.


## 7. Follow-up CI runner investigation (2026-11-15)

The Actions run list was queried directly for `feat/institutional-dashboard-design` after the prior audit.

| Workflow | Run | Commit | Attempt result | Job result |
|---|---:|---|---|---|
| Dashboard frontend checks | #9 / 43686597276 | `3fab6c7a7f4d47bffa8981c71a7366789dec8256` | Attempt 2 completed | Failure |
| Backend and dashboard tests | #1695 / 43692723553 | `4eeb7b9ba3b8fdc5925851ec3112169baad9a7ac` | Attempt 2 completed | Failure |

Both failed jobs were explicitly re-run. The rerun requests were accepted and produced new job IDs:
- Dashboard: `132782882178`
- Backend/dashboard: `132782892223`

Follow-up job inspection returned an empty `steps` array for both jobs. The job-log download endpoint returned an Azure `BlobNotFound` response for both. The observed job intervals were approximately three seconds, but this alone does not establish whether a runner was allocated or which setup stage failed. Runner name/ID and step-level output therefore remain unverified.

**Interpretation:** CI is confirmed failing at the workflow/job level, but the root cause is not diagnosable from the available Actions metadata because step details and logs are unavailable. Do not classify the dashboard tests themselves as failing; no test-step evidence was returned.

**Next diagnostic actions:**
1. Inspect the run in GitHub Actions UI and confirm whether a runner was assigned; capture the job's raw logs if GitHub retains them.
2. Check repository Actions settings, runner availability/permissions, and workflow execution restrictions without changing repository security settings.
3. If the run still has no steps/logs, trigger a controlled diagnostic workflow only after preserving the existing workflow behavior and confirming it cannot deploy.
4. Keep runtime/browser QA blocked until the feature-branch build is available in an isolated QA target. Do not repoint or deploy the existing staging service as part of this investigation.

## 8. Follow-up change-control confirmation

No changes were made to `main`. No PR was created or merged. No production or staging deployment was initiated. The CI rerun requests above did not modify application source or deployment configuration.


## 9. Runner allocation evidence (2026-11-15)

The GitHub Actions Jobs API was queried directly for the latest failed jobs. The returned job metadata explicitly reports:

| Run | Job ID | Requested labels | Runner ID | Runner name | Steps |
|---|---:|---|---:|---|---|
| #1696 | 132783385205 | `ubuntu-latest` | `0` | empty | `[]` |
| #1695 (attempt 2) | 132782892223 | `ubuntu-latest` | `0` | empty | `[]` |
| Dashboard #9 (attempt 2) | 132782882178 | `ubuntu-latest` | `0` | empty | `[]` |

This is stronger evidence than the earlier missing-log observation: for these three inspected jobs, GitHub's job metadata contains no assigned runner identity (`runner_id=0`, empty `runner_name`) and no executed steps. The jobs completed as failures within roughly 2–4 seconds. Therefore the evidence points to a runner assignment/dispatch problem before step execution, not to a demonstrated Python, Node, dashboard, or application test failure. The precise underlying cause (hosted-runner availability, repository Actions policy, billing/quota, service-side dispatch, or another GitHub-side condition) cannot be distinguished from the accessible metadata.

The workflow requests `ubuntu-latest`; its YAML defines normal checkout, Python 3.12, Node 22, syntax checks, dashboard tests, and pytest steps. No artifacts were published for Run #1696. Repository metadata confirms the repository is private and the connected GitHub identity has admin/push permissions, but the available API wrapper rejected direct reads of Actions runner inventory and Actions permissions endpoints. Those settings remain unverified.

**Required next action:** inspect the repository's Settings → Actions → Runners and Actions → General pages in GitHub, and the account/org Actions usage/billing limits. Confirm GitHub-hosted runner availability and that the repository is permitted to use GitHub-hosted runners. Do not weaken workflow permissions or deployment protections to work around this. After runner availability is restored, re-run the existing workflows and require non-empty runner identity, non-empty step records, and retained logs before treating CI as valid.


## 10. Latest CI and preview-environment inspection (2026-11-15)

After the runner-evidence update, push-triggered Backend and dashboard tests Run #1697 was created for commit `27df1503d925bc206f5809fd748cf3e848b5a042` and completed with failure. Its job ID is `132783645236`. The workflow-run-jobs response returned `steps: null` and `logs_url: null`; no artifacts were published. This is consistent with the prior runner-allocation anomaly, but this latest response did not expose runner_id/runner_name, so no additional runner identity claim is made for Run #1697.

A read-only Render workspace inspection found two existing web services for this repository. Both currently track branch `fix/binance-public-market-data-endpoints`, have auto-deploy disabled, and have pull-request previews disabled (`previews.generation=off`, `pullRequestPreviewsEnabled=no`). Neither is configured as an isolated preview of `feat/institutional-dashboard-design`. No service was created, changed, or deployed. Therefore there is currently no verified isolated Render preview target available for browser QA through the inspected services.

**QA gate:** do not run browser acceptance checks against either existing service and do not repoint either service to the feature branch. An isolated preview requires an explicitly approved, separate preview service or another non-production environment. Until then, responsive browser checks, keyboard interaction tests, runtime error simulation, Lighthouse, performance tracing, and memory profiling remain unexecuted and must remain marked pending.


## 11. GitHub Actions billing-budget root cause verified (2026-11-15)

Read-only inspection of GitHub Actions Run #1697 (run ID `43704861153`) in the authenticated GitHub UI exposed this exact failure annotation: 

> The job was not started because recent account payments have failed or your spending limit needs to be increased. Please check the 'Billing & plans' section in your settings

The run lasted approximately 3 seconds; the job never received a runner and no steps executed. This is an administrative Actions execution block, not evidence of a Python/JavaScript test failure.

A read-only inspection of the account's Billing Summary page showed no failed-payment, spending-limit, or account-restriction banner. However, a separate read-only inspection of **Settings → Billing → Budgets and alerts** showed five active budgets (Actions, Git LFS, All AI Credit SKUs, Packages, Codespaces); each displayed `$0.00 / $0.00`, `100%`, and `Usage blocked`. The Actions budget in particular is therefore visibly configured in a state that blocks usage. This is consistent with the Actions failure annotation. The Billing Summary's lack of a banner does not override the explicit budget-page block or the workflow failure annotation.

**Most likely actionable blocker:** the GitHub Actions budget is at a zero-dollar cap with usage blocked. The account owner must review the Actions budget under [GitHub Billing Budgets](https://github.com/settings/billing/budgets) and decide whether to set an appropriate non-zero budget / permit usage. If that does not clear the block, review the account's payment status in Billing & plans as the failure annotation also mentions recent payment failures. No budget, payment method, spending limit, or account setting was changed by this audit.

**Next verification gate:** after the account owner resolves the billing/budget restriction, rerun the latest failed job or push a deliberate QA commit and confirm a real runner ID, non-empty steps, and downloadable logs before treating CI as operational. Do not interpret the present failures as code-test results.
