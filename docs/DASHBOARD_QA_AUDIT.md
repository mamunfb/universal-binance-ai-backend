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


## 12. Static dashboard QA readiness review (2026-11-15)

A read-only source review was completed against the feature branch after identifying the Actions budget block. This is static inspection only; it is not a browser/runtime test and does not replace CI.

Checks observed:
- `dashboard/index.html` contains a viewport declaration, a main landmark, and the expected local script references (`./chart.js`, `./app.js`).
- The HTML contains no duplicate static element IDs. All 70 statically detected `$("id")` references in `dashboard/app.js` resolve to one of the 37 unique IDs declared in the HTML; no missing static ID references were detected.
- No inline HTML event-handler attributes were detected in the dashboard HTML.
- The dashboard stylesheet contains responsive breakpoints at 1100px, 760px, 480px, and 360px, plus `prefers-reduced-motion` and `:focus-visible` rules.
- The inspected app source uses request cancellation via AbortController, has bounded request timeouts, uses `textContent` for toast messages, and the only direct `innerHTML` assignment found in `app.js` clears the scan-summary container rather than interpolating remote response text.
- No `eval`, `new Function`, or localStorage use was detected in `dashboard/app.js`.

These are source-level observations only. They do not prove responsive layout correctness, focus order, screen-reader behavior, actual API behavior, performance, or memory stability. The next QA tasks remain blocked on a working execution environment: (1) owner resolves the Actions budget restriction, then obtain real CI runner/step/log evidence; and (2) provision an explicitly separate feature-branch QA preview before browser tests. Existing Render services must not be repointed or used for this purpose.


## 13. Dashboard-to-backend contract and accessible-name cross-check (2026-11-15)

A further read-only comparison was made between the feature-branch frontend and backend source:

- The Data Reliability selector offers exactly `1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d`. The backend `GET /api/v1/quality/market-data/{market}/{symbol}` route declares the same interval Literal values. No unsupported interval is exposed by that selector.
- The UI quality market options (`SPOT`, `USD_M`, `COIN_M`) match the route's market Literal values. The UI lookback validation (integer 1–2160 hours) matches the backend query bounds (`ge=1, le=2160`).
- All 16 static input/select controls have a programmatic accessible name through a wrapping label, a `for` label, or an explicit `aria-label`.
- All 22 static buttons have visible text or an explicit `aria-label`.

This cross-check confirms static contract alignment only. It does not establish successful requests against a running backend or assistive-technology behavior in a real browser. No application code was changed in this pass.


## 14. Billing gate and latest feature-branch CI confirmation (2026-11-15)

A fresh read-only inspection of the authenticated GitHub **Settings → Billing → Budgets and alerts** page reconfirmed the GitHub Actions budget state:

- Budget amount: **$0.00**
- Amount spent: **$0.00**
- Displayed utilization: **100%**
- Usage blocked: **Yes**

The page also displayed the same zero-budget / usage-blocked state for Git LFS, All AI Credit SKUs, Packages, and Codespaces. No billing, payment, spending-limit, or budget setting was changed.

The feature branch currently points to commit `32d26662e9b3c0bca013372b4b2529265b9585c5`. Its push-triggered **Backend and dashboard tests Run #1701** (run ID `43705469974`) completed with conclusion `failure`. The Jobs API returned job ID `132785482166`, status `completed`, conclusion `failure`, but `steps: null` and `logs_url: null`. Therefore this run does not provide evidence that Python tests or dashboard JavaScript checks actually executed; it remains consistent with the billing/runner gate, but its specific failure annotation was not independently re-read in this pass.

**Current gate:** the account owner must decide whether to allow GitHub Actions usage by changing the Actions budget / usage-block setting. Once authorized and resolved, rerun the existing workflow and verify an assigned non-zero runner ID, populated step records, and retrievable logs before interpreting CI results. No application code, workflow configuration, deployment configuration, main branch, PR, staging service, or production service was changed in this pass.


## 15. Frontend test-inventory and payload-scaling review (2026-11-15)

A read-only inventory of the current feature-branch test sources found **54 Node chart fixture tests** in `tests/test_dashboard_chart.js` and **110 Python dashboard contract tests** in `tests/test_dashboard_contract.py`. These are source-defined test cases, not a claim that they executed or passed. The chart fixtures cover OHLCV parsing, duplicate timestamps, 3h aggregation, indicator reference values, malformed data, numerical extremes, request supersession/invalidation, and the 1,000-source-row chart processing cap. The Python contract tests additionally cover scanner sorting/pagination, stale-response handling, request cancellation, credential handling, and dashboard markup contracts.

Two payload-scaling areas remain unmeasured and deserve explicit runtime coverage:

1. The shared browser API helper reads the complete response with `response.text()` before JSON parsing; the inspected client code does not impose a response-byte ceiling. A very large or unexpectedly streamed backend response could therefore increase browser memory use before schema validation. No exploit or actual memory failure was demonstrated.
2. Scanner rendering filters and sorts the complete accepted row array before displaying a 100-row page. Pagination limits DOM rows, but does not itself limit the size of the response or the in-memory sort/search work. No large-market benchmark or browser memory profile has been run.

The chart loader separately truncates candle input to the latest 1,000 rows before parsing/indicator calculation; this is a source-level bound, not a measured performance result. Future isolated QA should add representative small/large scanner payload benchmarks, API response-size stress cases, and memory/render timing measurements before choosing any hard cap or changing backend contracts.

The latest feature-branch commit at the time of this review was `acdc2bf41ecd7316fe75fa07d69a15da88ba2afc`. Push-triggered **Backend and dashboard tests Run #1702** (run ID `43705633456`) completed with conclusion `failure`; job ID `132785971930` returned `steps: null` and `logs_url: null`. The Actions budget was independently confirmed in Section 14 as zero with usage blocked. Run #1702 therefore supplies no test-execution evidence; do not interpret it as an application test failure.

No application code, workflow, backend contract, deployment configuration, main branch, PR, staging service, or production service was changed in this review.



## 16. Latest feature-branch runner and evidence recheck (2026-11-15)

The feature-branch ref was read directly from GitHub and resolves to **`0cae08ef7fde3b61b714cca3d7d4e092cd791c18`** (commit message: “Document dashboard test inventory and payload scaling risks”). The push-triggered **Backend and dashboard tests Run #1703** (run ID `43705706619`) is associated with that exact head SHA and completed with conclusion `failure`.

The latest-attempt Jobs API returned job ID `132786195964`, conclusion `failure`, `logs_url: null`, and `steps: null`. A separate job-steps lookup returned an empty array. The job-log download request returned an Azure `BlobNotFound` response, and the run-artifacts lookup returned no artifacts. Thus Run #1703 provides no evidence that checkout, Python/Node setup, syntax checks, chart fixtures, dashboard contract tests, or pytest executed. It must not be reported as an application-test failure or pass.

The branch workflow file `.github/workflows/dashboard-frontend.yml` was also read back. It has a manual `workflow_dispatch` trigger and path-filtered push/PR triggers for dashboard files, dashboard tests, the implementation-status document, and its own workflow file. The latest commit changed only the QA audit report, so it does not satisfy that workflow's listed push paths; no manual dispatch was performed. The general `.github/workflows/tests.yml` does trigger on every push to this feature branch and produced Run #1703.

**Current verified state:** feature branch head is `0cae08e...`; Run #1703 is a workflow/job failure with no executed-step or log evidence; the zero-dollar Actions usage-block state documented in Sections 11 and 14 remains the known administrative blocker. The precise failure annotation for Run #1703 was not available from the job/log endpoints in this pass, so the billing gate is consistent with the failure but is not re-proven as the specific annotation for this individual run.

**Next safe actions:** account owner resolves the Actions budget/usage-block setting; then re-run the existing workflows and verify non-zero runner identity, populated steps, and retrievable logs. After CI execution is restored, run the existing dashboard fixture and contract suites, then proceed to isolated browser/runtime and payload-scale QA. No workflow, application source, deployment configuration, main branch, PR, staging service, production service, or billing setting was changed in this pass.


## 17. Exact GitHub Actions failure annotation confirmed in browser (2026-11-15)

A read-only authenticated GitHub Actions page inspection was completed for Run #1703 (`43705706619`). The failed job displayed this exact annotation:

> The job was not started because recent account payments have failed or your spending limit needs to be increased. Please check the 'Billing & plans' section in your settings

The Actions page showed that no runner was assigned and no steps or logs were available. This confirms that Run #1703 stopped before workflow execution because GitHub blocked job startup on an account billing / spending-limit condition. It is not evidence of a failing Python test, JavaScript syntax check, dashboard fixture, or application defect.

A fresh Actions run-list query after the latest audit commit found **Backend and dashboard tests Run #1704** (run ID `43705802334`) for head commit `3f5bbf0b18f04412e9f726740aa9825ad2fb7c15`. Its job ID is `132786485790`; the Jobs API again reports conclusion `failure`, `steps: null`, and `logs_url: null`. The exact UI annotation for Run #1704 was not separately inspected, so it is recorded as matching the same pre-execution failure pattern, not as a separately confirmed annotation.

**Required owner action remains:** review GitHub **Billing & plans** and **Settings → Billing → Budgets and alerts**, resolve any failed-payment or spending-limit restriction, and ensure Actions usage is permitted. No payment method, billing budget, spending limit, or account setting was changed during this audit.

No source code, workflow, branch protection, deployment configuration, PR, staging service, or production service was changed in this pass.


## 18. Account billing restriction recheck and latest CI confirmation (2026-11-15)

A second read-only inspection of GitHub Settings → Billing → Budgets and the latest Actions Run #1705 confirmed the restriction is still active.

All five displayed account budgets are blocked at 100% utilization with a displayed allowance/spend of **$0.00 / $0.00**:
- Actions — usage blocked
- Git LFS — usage blocked
- All AI Credit SKUs — usage blocked
- Packages — usage blocked
- Codespaces — usage blocked

The latest Run #1705 UI displayed the pre-start failure message: **“The job was not started because recent account payments have failed or your spending limit needs to be increased. Please check your billing settings.”** The Jobs API for Run #1705 independently reports the job as failed with `steps: null` and `logs_url: null`. This is a confirmed account billing / spending restriction, not an executed test failure.

No billing settings, payment methods, spending limits, CI reruns, workflows, application files, PRs, staging, or production were changed. The repository owner must resolve the payment or spending restriction in GitHub billing settings before genuine CI execution can be assessed.


## 19. Dashboard source and regression-coverage inventory (2026-11-15)

A further read-only source pass compared the current dashboard files and existing regression tests on the feature branch. The inspected source SHAs remain:
- `dashboard/app.js`: `dab6a9f61609eae51f68f9517d8b9da4c48a91f3`
- `dashboard/app.css`: `9b840e191b91464692a4dfdda2d6a3f464ad9cd2`
- `dashboard/index.html`: `2172461b561fa19e31a46c095d3f8c0f5c95b3e2`
- `dashboard/chart.js`: `7fabc870e21adf6805c7766b29803cb4d66cd87b`
- `tests/test_dashboard_contract.py`: `4d53dcb01d688f9278a4a624e56ac9c1314b6cda`
- `tests/test_dashboard_chart.js`: `16749d250e5426336c88bbe5ebd267e850611491`

**Static inventory findings (not runtime results):**
- HTML contains 79 unique element IDs; no duplicate IDs were found by source scan.
- The document references the local `chart.js` and `app.js` scripts; chart script precedes app script.
- CSS includes responsive breakpoints at 1100px, 760px, 480px and 360px, plus `prefers-reduced-motion`.
- The Python contract file contains 110 test methods and 507 `self.assert...` occurrences.
- The Node chart fixture file contains 54 named test cases.
- Existing tests explicitly cover mobile navigation state/focus, scanner pagination/focus, stale-request cancellation, API timeout vs caller cancellation, malformed scanner values, chart parsing/aggregation, indicator numerical extremes, and the 1,000-source-candle processing bound.

**Additional unverified runtime/performance questions retained for isolated QA:**
1. The browser API wrapper reads the entire response with `response.text()` before JSON parsing; no response-byte ceiling or streaming parser was found in `app.js`.
2. Scanner filtering and sorting traverse the full accepted row set before slicing the current 100-row DOM page; no server-side scanner pagination contract was found in the inspected client path.
3. The inspected chart renderer creates an SVG and several indicator panels; resize-observer-based redraw and explicit chart observer teardown hooks were not found. This is a profiling question, not a confirmed defect.
4. Page lifecycle cleanup hooks (`pagehide` / `beforeunload`) were not found in the inspected app source; no leak or stuck-request behavior has been demonstrated.

**Disposition:** no application code change is justified from static inspection alone. Do not introduce arbitrary response caps or alter scanner pagination/API contracts without representative payload measurements and backend compatibility tests. The above 110 Python and 54 Node cases remain source-defined only; none is marked passed because the GitHub Actions billing restriction has prevented runner startup. No production, staging, main branch, PR merge, or billing setting was modified.


## 20. CI status after expanded source audit (2026-11-15)

The push of the prior billing recheck report commit `2ebcc33f2b320af85dbcb22e32a9dd1b11657dad` triggered **Run #1706** (run ID `43706114829`). Its job ID is `132787442341`; the Jobs API reports conclusion `failure`, `steps: null`, and `logs_url: null`. This is consistent with the previously browser-confirmed billing block, but no separate browser annotation was captured for Run #1706. It supplies no evidence that the Python or Node test steps ran.

The expanded source/coverage review in Section 19 is documentation-only. It does not change the application or workflow and does not resolve the account restriction. The latest source-level conclusions therefore remain unchanged: test cases are defined but not executed; runtime/browser/performance results are pending; arbitrary payload caps or API pagination changes remain deferred until measured.


## 21. Run #1708 runner-start failure confirmed in GitHub UI (2026-11-15)

A read-only inspection of the GitHub Actions page for **Backend and dashboard tests Run #1708** (run ID `43706217125`) confirmed the exact failure condition for the latest feature-branch commit `fb9b4f4af8f46446199f91e90b8d1596b8e9225d`.

The visible annotation states:

> The job was not started because recent account payments have failed or your spending limit needs to be increased.

The job **Python tests and dashboard JavaScript validation** was not started, no runner was assigned, and zero workflow steps executed. The Jobs API reports job ID `132787754211`, conclusion `failure`, `steps: null`, and `logs_url: null`; a separate step lookup returned an empty array, the log download returned Azure `BlobNotFound`, and the run has no artifacts.

**Conclusion:** Run #1708 is an account payment / spending-limit gate before runner allocation. It provides no evidence for either success or failure of Python tests, JavaScript validation, dashboard behavior, or application code. The ubuntu-latest migration annotation is informational and is not the cause of this run's failure.

**Next action:** the repository/account owner must resolve the GitHub payment or spending-limit restriction. Once resolved, re-run the existing workflow and verify that a runner is assigned, step records are populated, and logs are retrievable before interpreting test outcomes.

No billing setting, workflow, application source, main branch, PR, staging service, or production service was changed during this check.


## 22. Follow-up CI run #1709 confirms the same pre-run billing gate (2026-11-15)

The Section 21 documentation commit `85c60e86adeb01b6c56c41669677af4aec42901e` triggered **Run #1709** (run ID `43706390914`). A read-only GitHub Actions UI inspection independently confirmed the same account-level restriction.

The exact visible annotation reads:

> The job was not started because recent account payments have failed or your spending limit needs to be increased. Please check the 'Billing & plans' section in your settings.

The run lasted approximately three seconds. No runner was assigned and no workflow steps executed. The Jobs API reports job ID `132788286526`, conclusion `failure`, `steps: null`, and `logs_url: null`.

**Interpretation:** the documentation-only commit itself did not cause a code/test failure. Run #1709 was blocked before execution by the GitHub account payment / spending-limit restriction. The repeated UI confirmation across Runs #1708 and #1709 makes the administrative blocker conclusive for these two runs. Actual dashboard/browser/runtime QA and all CI test outcomes remain unverified until GitHub permits runner startup.

No billing, workflow, application source, main branch, PR, staging, or production settings were changed.


## 23. Latest feature-branch CI run #1710 inspection (2026-11-15)

A fresh read-only Actions API check found **Backend and dashboard tests Run #1710** (run ID `43706451197`) on feature-branch commit `7c0eed163fcc53ec622c0ecc7657eb7969cf127c`.

The Jobs API reports:
- Job ID: `132788476726`
- Job name: `Python tests and dashboard JavaScript validation`
- Job conclusion: `failure`
- `steps: null`
- `logs_url: null`

A separate job-step lookup returned an empty array (`[]`). A read-only authenticated GitHub Actions UI inspection then confirmed the exact annotation:

> The job was not started because recent account payments have failed or your spending limit needs to be increased. Please check the 'Billing & plans' section in your settings.

The UI also confirmed that no runner was assigned, no workflow steps ran, and logs are unavailable. This directly confirms the account payment / spending-limit gate for Run #1710. Do not classify it as a Python, Node, dashboard, or application test failure.

For comparison, Run #1709 (run ID `43706390914`, job ID `132788286526`) also returned `steps: null`, `logs_url: null`, and an empty step lookup. Its exact GitHub UI billing annotation is documented in Section 22.

**Current CI gate:** Runs #1708, #1709, and #1710 have direct UI confirmation of the account payment/spending-limit block. The owner must resolve the account-level Actions restriction, then obtain a new run with a non-zero runner ID, populated step records, and retrievable logs before interpreting test outcomes.

No workflow, application source, `main`, PR merge state, staging service, production service, or billing configuration was changed during this inspection.


## 24. First actual feature-branch CI execution after Public visibility (2026-11-15)

After the repository became public, failed job `132788476726` from Run #1710 was re-run as **Attempt 2**. GitHub allocated a hosted runner and the workflow executed, establishing that the previous account-level runner-start block no longer prevented this attempt from starting.

**Run:** [#1710 Attempt 2](https://github.com/mamunfb/universal-binance-ai-backend/actions/runs/43706451197)  
**Commit tested:** `7c0eed163fcc53ec622c0ecc7657eb7969cf127c`  
**Job ID:** `132807793811`

Step evidence:
- Set up job — success
- Checkout — success
- Python 3.12 setup — success
- Node.js 22 setup — success
- Runner toolchain verification — success
- Python dependency installation — success
- Dashboard HTML/script-reference validation — success
- Dashboard JavaScript syntax validation — success
- Python test suite — **failure**
- Final job conclusion — **failure**

The retained job log reports **31 failed, 609 passed, 2 warnings** in the Python test suite (3.77 seconds). This is the first verified test execution in this sequence; unlike Runs #1708–#1710 Attempt 1, this result includes an actual application test outcome.

Failure inventory from the log:
- 10 failures in `tests/test_dashboard_contract.py`, predominantly exact source-string / substring expectations that no longer match the current dashboard implementation (for example older Escape-key handling expression, scanner helper extraction boundaries, timezone refresh expression and Stochastic RSI declaration spelling).
- 20 failures in `tests/test_dashboard_quality_markup.py`, whose assertions expect the previous dashboard's camelCase element IDs and inline HTML JavaScript/renderers. The current feature branch uses the split `dashboard/index.html`, `dashboard/app.js`, and `dashboard/chart.js` architecture with kebab-case IDs and generic JSON display for the Data Reliability response. These failures show test/source contract mismatch; they do not by themselves establish that the equivalent user-visible capability is correct or incorrect.
- 1 failure in `tests/test_news_intelligence.py::test_collect_news_marks_items_unverified_and_reports_coverage`. The RSS fixture is dated 2026-11-10 while the CI run occurred 2026-11-15 and the service default window is 72 hours. The fixture item is filtered as stale, then the test indexes an empty `items` list. This is a time-dependent test-fixture defect; the production freshness filter should not be weakened to make the old fixture pass.

**Disposition:** CI is now genuinely executing. The Python suite is not green. Do not change production logic or weaken assertions blindly. Next work should (1) modernize static contract tests to assert current behavior rather than brittle old source snippets, (2) decide whether the advanced Data Reliability metrics need dedicated structured UI rendering or whether raw JSON is the accepted design, and (3) make the news test fixture deterministic relative to the 72-hour window. Re-run the full suite after reviewed corrections.

No backend application logic, production deployment, staging service, `main`, PR merge state, or billing settings were changed during this diagnostic rerun.
