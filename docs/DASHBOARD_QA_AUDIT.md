# Dashboard QA & Implementation Audit

**Date:** 2026-11-15  
**Working branch:** `feat/institutional-dashboard-design`  
**Latest browser-tested source commit:** `8d10f175d62da6edb2fa53bec4a948d6240eee2c`  
**Scope:** dashboard CI, responsive layout, keyboard accessibility, JavaScript/API handling, rendering performance.  
**Change-control boundary:** `main`, PR merge state, and production deployment are intentionally unchanged.

## Executive status

This is a feature-branch source and isolated-browser audit, not a release-readiness sign-off. The current staging URL still serves a different, older dashboard implementation; staging observations below are not runtime verification of the feature branch.

| Area | Current evidence | Status |
|---|---|---|
| GitHub Actions runner | Browser QA Run #31 and backend Run #1793 completed with retrievable job logs | **Verified** |
| Feature-branch mobile layout | Chromium tested 360, 390, 480, 760, 768, 1100 and 1280 CSS-pixel widths without horizontal overflow | **Browser PASS** |
| Feature-branch keyboard navigation | Mobile focus trap, Escape/focus restoration, and keyboard sorting on a 1,000-row scanner fixture | **Browser PASS** |
| JavaScript/API errors | Mocked health success, HTTP 503, malformed JSON, network failure, empty response, invalid shape, timeout and stale-scan cancellation | **Browser PASS; live API not tested** |
| Large-dataset rendering | 1,000 mocked rows; 100 DOM rows per page; search and pagination verified | **Browser PASS; no timing/heap benchmark** |
| Automated accessibility | axe-core 4.10.3, WCAG 2.1 A/AA tags, zero violations on initial visible dashboard | **Automated scan PASS; not full WCAG certification** |
| Browser QA on staging | Staging still serves a different dashboard implementation | **Staging-only; not feature branch** |

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

**Historical note:** the first audit checkpoint lacked a verified runner job and log. This gap was subsequently resolved: Browser QA Run #31 (job `132835163790`) and Backend + Dashboard Run #1793 (job `132835163796`) both completed successfully on source commit `8d10f175d62da6edb2fa53bec4a948d6240eee2c`. Their actual step and test logs are recorded in Section 31; those results supersede the initial pending status.

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


## 25. Full CI green after test and numerical-safety corrections (2026-11-15)

Both feature-branch workflows completed successfully on commit `f95e5afd4690b56ab91b7ae2e704bfdc5a16a9af`.

**Backend and dashboard tests — Run #1723**
- Run ID: `43713781865`
- Job ID: `132811050272`
- Conclusion: **success**
- Pytest: **625 passed, 2 warnings in 5.04s**
- All workflow steps succeeded: Python 3.12 setup, Node 22 setup, dependency installation, dashboard HTML/script-reference validation, dashboard JavaScript syntax checks, and the full Python suite.

**Dashboard frontend checks — Run #16**
- Run ID: `43713781843`
- Job ID: `132810816183`
- Conclusion: **success**
- Dashboard JavaScript syntax checks: success
- Node chart fixtures: success (**53 tests**, as reported by the preceding run log after the four fixture/implementation corrections)
- Dashboard Python contract tests: success (**110 unittest cases**)

Corrections included:
1. Stabilized `finiteMean` by scaling finite inputs and using compensated summation. This removed a large cancellation error for alternating `±Number.MAX_VALUE` values.
2. Bollinger series now preserves a representable middle/SMA value even when upper/lower bounds overflow; only unrepresentable bounds remain unavailable.
3. Corrected the 3h aggregation fixture to pass parsed candle objects, corrected post-gap indicator warm-up expectations, and completed the DOM test double's DocumentFragment behavior.
4. Made the news-intelligence test deterministic by explicitly using a seven-day test window for its fixed historical RSS fixture. Production freshness logic remains unchanged.
5. Refreshed brittle dashboard source-contract assertions to match the current SPA's actual abortable API calls, validation ordering, cached timestamp refresh, and keyboard Escape behavior.
6. Replaced legacy inline/camelCase quality-markup checks with tests for the current split SPA controls, verified route, input validation, shared API client and text/JSON response rendering.

**Scope qualification:** green CI proves the automated checks in these workflows passed for this commit. It does not prove live backend connectivity, browser viewport behavior, screen-reader behavior, live exchange data correctness, performance profiling or full structured Data Reliability/collector/Neon/R2 rendering. Those remain separate QA tasks.

No `main` changes, PR merge, staging deployment, production deployment, billing change or backend service logic change was made in this pass.


## 26. Static accessibility and responsive contract expansion (2026-11-15)

Added `tests/test_dashboard_accessibility.py` using Python's standard-library HTML parser. It checks:
- duplicate HTML IDs and required main/navigation/header landmarks;
- accessible labels for every static input/select/textarea;
- accessible names for every static button;
- mobile sidebar `aria-controls`/`aria-expanded`, inert state and Escape-key close contract;
- 1100/760/480/360px responsive breakpoints and reduced-motion declaration;
- keyboard focus indicators for navigation, form controls, pagination and named table regions.

The Dashboard frontend workflow now discovers all `test_dashboard_*.py` tests and watches the new test file.

**CI evidence on commit `a5782637d3861c2a5a060b194ef9caeee25dea3c`:**
- Dashboard frontend Run #18, job `132813709715`: **success**; 116 Python dashboard contract/accessibility tests passed, and the existing JavaScript syntax and Node chart-fixture steps passed.
- Backend and dashboard Run #1728, job `132813716961`: **success**; **631 passed, 2 warnings in 5.14s**.

**Limit:** These are static markup/source/CSS contract checks. They are not a real Chromium/WebKit mobile viewport run, screen-reader session, keyboard interaction session, or visual regression test. Those still require a browser-served build and an approved QA environment; no deployment was performed.


## 27. Latest feature-branch CI and source-level API/performance review

**Verified HEAD:** `ff39adc7d9d013215d5e1af3e79e3913a7560f8a`  
**Verification date:** 2026-11-15

### CI evidence on the verified HEAD

- Dashboard Frontend workflow run #19 completed successfully. Its job log records JavaScript syntax checks, chart fixtures, and **116 Python dashboard tests passed**.
- Backend + Dashboard workflow run #1730 completed successfully. Its job log records dashboard document/script-reference validation, JavaScript syntax checks, and **631 pytest tests passed with 2 warnings**.
- These are CI results for the feature branch HEAD above; they do not constitute browser/device QA.

### Source-level API/runtime handling review

Reviewed `dashboard/app.js` at the verified HEAD:

- API requests use an AbortController, a finite positive timeout, optional caller cancellation, and cleanup of timeout/event listeners.
- Non-JSON, empty successful JSON, non-2xx responses, timeout, cancellation, and network TypeError paths are converted into explicit errors.
- Backend-provided detail text is control-character stripped, whitespace-normalized and length-limited before being surfaced.
- Credentials are held in page memory; remote backend URLs require HTTPS, and embedded credentials/query/hash are rejected.
- Request sequence counters and cancellation controllers are used by scanner, health, readiness, quality and analysis flows to reduce stale-response rendering.
- No runtime exception telemetry, real API fault injection, or browser console capture was performed. This remains source review, not runtime proof.

### Source-level rendering/performance review

- Scanner text and numeric sort keys use WeakMap caches.
- Scanner search input is debounced (150 ms); rendered table rows are batched with DocumentFragment; pagination limits the rendered page to 100 rows.
- Chart rendering is bounded to the most recent 120 candles (per source-level test coverage).
- The full API response remains in browser memory; no virtualization, memory profiling, Lighthouse run, or measured frame/paint benchmark was performed.

### Remaining verification

- Real browser viewport testing of this exact feature-branch build at mobile and desktop widths.
- Keyboard-only and screen-reader testing in a browser.
- API fault-injection tests for timeout, cancellation, malformed JSON, HTTP errors and stale responses.
- Lighthouse/Core Web Vitals and memory/render profiling.
- Existing two dependency/framework deprecation warnings should be reviewed separately; they did not fail the CI run.

No backend code, database, secrets, billing, main branch, PR merge state, or deployment settings were changed in this audit.


## 28. API and keyboard regression contract expansion

**Source checkpoint tested:** `6806f7812898f9458d6a4f62d59eba90d5e4761f`

Added three static regression checks to `tests/test_dashboard_accessibility.py`:
- API wrapper contracts for finite timeout validation, AbortController/caller cancellation, JSON parsing, HTTP/non-JSON/empty-response errors, network errors and cleanup.
- Backend URL validation for HTTPS-only remote URLs and rejection of embedded credentials, query strings and fragments.
- Mobile navigation focus restoration, Escape exit and Tab/Shift+Tab boundary handling.

Updated `.github/workflows/dashboard-frontend.yml` so pull-request path filters also run the accessibility test file. Previously the push path filter included it but the pull-request path filter did not.

### CI evidence on this checkpoint

- Dashboard Frontend run #? (run ID `43717409892`): **success**; 119 dashboard Python tests passed, chart fixtures and JavaScript syntax checks passed.
- Backend + Dashboard run (run ID `43717409851`): **success**; **634 passed, 2 warnings**; dashboard document/script-reference and JavaScript syntax checks passed.

These are static/source contract tests. They do not simulate a real browser, screen reader, live backend failure or measured rendering performance. Those remain pending.


## 29. Real Chromium browser QA and tablet responsive correction

**Verified feature-branch HEAD:** `96db94ccd87a88e5050e397f17527a6babda78c6`  
**Browser workflow:** Dashboard browser QA run #9, run ID `43718964746`  
**Runner:** Ubuntu 24.04, pinned Playwright 1.56.1, Chromium headless  
**Verification date:** 2026-11-15

### Browser test results

The isolated browser workflow served the exact feature-branch dashboard files from a local test server. No production deployment or live backend was used.

| Browser test | Result |
|---|---|
| Responsive layout at 360, 390, 480, 760, 768, 1100 and 1280 CSS px | **PASS** — no document/body horizontal overflow |
| Mobile navigation open/close and ARIA state | **PASS** |
| Shift+Tab / Tab focus boundary wrapping | **PASS** |
| Escape closes navigation and restores focus to menu button | **PASS** |
| Mocked backend health success | **PASS** |
| Mocked HTTP 503 error handling | **PASS** |
| Mocked malformed JSON response handling | **PASS** |
| Browser page-level JavaScript exceptions in tested paths | **None observed** |

Node test summary from the completed Actions log: **4 tests, 4 passed, 0 failed**.

### Defect found and corrected

The first real Chromium viewport pass detected horizontal overflow at **768px**: document width was 908px while the viewport was 768px. The tablet layout was still using the desktop sidebar/header arrangement.

Correction:
- Moved the responsive off-canvas navigation breakpoint from 760px to 900px in `dashboard/app.css`.
- Aligned the JavaScript mobile-navigation media queries in `dashboard/app.js` to 900px.
- Updated the static accessibility breakpoint assertion.
- Re-ran the full viewport matrix; the completed run reports no horizontal overflow at all seven widths.

The browser pass also verified the mobile keyboard focus correction: opening navigation now focuses the first keyboard-focusable sidebar item, matching the boundary-trap sequence.

### CI evidence

- Dashboard browser QA run #9, `43718964746`: **success**, 4/4 browser tests passed.
- Backend + Dashboard run #1751, `43718964792`: **success**, **634 passed, 2 warnings**; HTML/script references and dashboard JavaScript syntax checks passed.
- Dashboard Frontend run #31, `43718841160`: **success**, **119 dashboard Python tests**; chart fixtures and JavaScript syntax checks passed.

### Scope and remaining limits

- API fault tests use deterministic browser route mocks for HTTP 503 and malformed JSON; they do **not** contact the live backend or prove production API availability.
- This run does not constitute a screen-reader/assistive-technology test, physical-device test, Lighthouse/Core Web Vitals run, memory profile or measured performance benchmark.
- Render still serves a different deployment branch; no feature-branch deployment was made.

No merge, production deployment, backend/database mutation, secret change or `main` branch update was performed.


## 30. Expanded Chromium API-failure and accessibility regression suite

**Verified baseline:** dashboard source `86358ccad4bbb942e3f11d0ebedaca93c3295236`; browser test source `f82f0a445ce47ad3e69f2d66b98cb699613c5402`  
**Verification date:** 2026-11-15

Expanded `tests/test_dashboard_browser.cjs` from four to eight independent Node/Playwright tests. New browser coverage includes:
- network-level request failure;
- successful HTTP status with an empty response body;
- a JSON array where the health endpoint contract requires an object;
- request timeout handling (the test shortens only the browser timer in its isolated page context and delays a mocked route);
- changing the selected market while a scan is in flight cancels the stale request and prevents stale rendering;
- initially closed mobile sidebar is inert;
- document main/header landmarks and a navigation landmark with an explicit accessible name;
- reduced-motion CSS behavior.

Existing browser tests continue to cover the seven viewport widths, mobile keyboard focus wrapping, Escape/focus restoration, mocked health success, HTTP 503 and malformed JSON.

**CI execution evidence:** GitHub Actions browser QA Run #16 (`43719647421`) executed the prior eight-test checkpoint (`5e73bbbbcc88cc92d0335cae848eab446be689dd`). The runner completed tests 1–7 successfully and failed test 8 after a 30-second wait for Playwright's `requestfailed` event timed out. The log reports **7 passed, 1 failed**. This is a browser-test synchronization/assertion failure; the log does not establish a dashboard application regression.

**Harness and UI corrections:** the cancellation regression instruments the browser fetch signal and waits for the actual `AbortSignal` event, not Playwright's routed-request `requestfailed` event. It waits for the mocked route handler to settle and returns to Overview before starting the scan. Run #19 (`43720275007`) then exposed a genuine status-label defect: changing the global-market dropdown aborted the scan but left the label at `Refreshing · previous results retained`. The global-market handler now announces `Market selection changed · run a new scan` when it invalidates an active scan.

**Verified pass:** GitHub Actions browser QA Run #20 (`43720395219`) on commit `86358ccad4bbb942e3f11d0ebedaca93c3295236` completed successfully. The actual job log records **8 tests, 8 passed, 0 failed** (11.45 seconds). This is the first verified all-green result for the expanded eight-test browser suite.

The API cases use browser route mocks and a local static dashboard server; they do not exercise a live backend. No production endpoint, credentials, trading action, database, deployment, or main-branch state is touched by these tests.

**Additional accessibility assertions verified:** browser-test commit `3f9e1a4a87faa5dc9cd570660712ad24a1b3e645` checks the mobile menu's accessible name across open/closed states and verifies the primary navigation landmark and active-page `aria-current` state. GitHub Actions Run #22 (`43720574539`) passed these assertions; the log records **8 passed, 0 failed**. The job completed successfully in 38 seconds. It emitted one non-blocking Node.js 20 deprecation warning because the workflow still referenced `actions/checkout@v4` and `actions/setup-node@v4`.

**Workflow runtime maintenance:** the browser, frontend, backend-test and scheduled market-scan workflows have now been updated to `actions/checkout@v7`; workflows that use Node setup use `actions/setup-node@v7`, and Python setup uses `actions/setup-python@v7`. Node package-manager auto-caching is explicitly disabled where it is not needed.

- Browser QA Run #23 (`43720755588`, workflow action update commit `56dd1f2`): **8 passed, 0 failed**; no Node.js 20 deprecation annotation.
- Dashboard Frontend Run #36 (`43720861103`, setup-python update commit `2d281e0`): **53 passed, 0 failed**; no Node.js 20 deprecation annotation.
- Backend Run #1784 (`43720886522`, commit `0887ac2`): **634 passed, 0 failed**; two existing Python deprecation warnings (Starlette/httpx TestClient integration and FastAPI's deprecated `example` parameter), but no Node.js 20 action-runtime warning.

The scheduled market-scan workflow was updated to the v7 actions but was not manually dispatched; its schedule and secret-backed scan were deliberately left untouched. The action upgrades are verified on the browser, frontend and backend-test workflows.

Next verification is to broaden the accessibility and performance regression checks while preserving the verified eight-test baseline.

No merge, production deployment, backend/database mutation, secret change, or `main` branch update was performed.


## 31. Large-dataset Chromium stress test and WCAG contrast correction

**Verified feature-branch checkpoint:** `8d10f175d62da6edb2fa53bec4a948d6240eee2c`  
**Verification date:** 2026-11-15

### New browser coverage

Expanded `tests/test_dashboard_browser.cjs` from 8 to 10 independent Chromium tests:
- A 1,000-row mocked Spot Scanner response at a 390px mobile viewport.
- Confirms the rendered table is bounded to 100 rows per page (10 pages for 1,000 results), not 1,000 simultaneous DOM rows.
- Exercises keyboard sorting (Enter on the Symbol column), debounced search, pagination to page 2, and document/body horizontal-overflow checks.
- Runs axe-core 4.10.3 against the visible initial dashboard using WCAG 2.1 A/AA tags.

### Defect found and corrected

The first axe-core pass identified a contrast failure in the four metric-card captions: foreground `#71839f` on `#111b2d` measured 4.47:1, just below the 4.5:1 WCAG AA threshold for normal text.

Changed only the `.metric-card small` foreground to `#7486a2` (calculated contrast approximately 4.66:1 against the same card background). The subsequent Chromium axe-core audit reports **zero WCAG 2.1 A/AA violations** for the tested initial dashboard view.

The 1,000-row test also required two harness corrections: scope pager locators to the Spot Scanner (three scanner tables each create a pager), and wait for the debounced filtered-count update before asserting the result count. These were test synchronization/selector defects, not dashboard application defects.

### Verified CI evidence

- Dashboard browser QA Run #31: [run 43721786692](https://github.com/mamunfb/universal-binance-ai-backend/actions/runs/43721786692), job `132835163790`: **10 tests, 10 passed, 0 failed** (14.62 seconds).
- Backend + Dashboard Run #1793: [run 43721786675](https://github.com/mamunfb/universal-binance-ai-backend/actions/runs/43721786675), job `132835163796`: **634 passed, 2 warnings** (4.99 seconds).
- Dashboard Frontend Run #37: [run 43721596752](https://github.com/mamunfb/universal-binance-ai-backend/actions/runs/43721596752), job `132834569924`: **119 dashboard contract/accessibility tests passed**; chart fixtures and JavaScript syntax checks succeeded.

### Limits that remain

- The 1,000-row dataset is deterministic mocked browser data. This verifies client-side pagination, search, sorting and mobile layout, not production exchange payload sizes or live API throughput.
- The axe-core run covers the initial visible dashboard state. It is an automated accessibility scan, not a screen-reader session, manual keyboard review of every route, or complete WCAG conformance certification.
- No Lighthouse/Core Web Vitals run, CPU throttling, paint/frame timing benchmark, heap snapshot, or long-duration memory profile was performed. The 1,000-row test verifies bounded DOM row count, not measured rendering speed.
- Live backend/API connectivity and physical-device behavior remain outside this isolated local-server test.

No backend business logic, database, secrets, billing, `main`, PR merge state, staging or production deployment was changed.


## 32. Performance QA execution gate and benchmark plan (2026-11-15)

**Review scope:** Lighthouse/Core Web Vitals, JavaScript heap/memory profiling, and CPU-throttled rendering benchmark.

### Current evidence and execution status

The current feature-branch audit still has no measured Lighthouse report, Web Vitals trace, heap snapshot, retained-heap comparison, or CPU-throttled timing result. The previously verified 1,000-row Chromium test establishes bounded table DOM pagination (100 visible rows), search/sort interaction, and absence of horizontal overflow at the tested viewport. It does **not** establish render latency, CPU cost, heap growth, garbage-collection behavior, or Core Web Vitals.

The latest inspected CI checkpoint, Backend and dashboard tests Run #1708 (run ID `43706217125`), returned one completed failed job (job ID `132787754211`) with `steps: null` and `logs_url: null`. This does not prove that a performance command or application test executed. The existing Actions budget restriction recorded earlier in this report remains an execution blocker unless independently resolved.

The existing Render services were previously inspected and found to serve a different branch/dashboard implementation. They are not valid targets for measuring this feature branch. No service was repointed and no staging or production deployment was attempted. No local feature-branch browser/DevTools runtime was available in this GitHub source-inspection session. Consequently, running Lighthouse against the old staging page or reporting source-derived estimates as measurements would produce misleading evidence.

### Planned combined benchmark protocol (not yet executed)

1. **Lighthouse / Web Vitals:** serve the exact feature-branch dashboard in a disposable isolated QA runtime; run mobile Lighthouse at a fixed viewport and network profile for at least three cold-load samples; retain each JSON/HTML report and report the median LCP, CLS, FCP, Speed Index and TBT. Treat INP as a field metric requiring real user interaction data; do not infer it from TBT. Record browser, Lighthouse version, device emulation, network profile, cache state and commit SHA.
2. **Heap and memory:** capture a baseline heap snapshot after initial idle; load the 1,000-row scanner fixture; repeat search, sort, pagination and chart symbol/timeframe changes; capture a second snapshot after cleanup/settling. Compare retained heap, detached DOM nodes and listener/object retention. Repeat the interaction cycle to distinguish one-time allocation from continuing growth. Preserve snapshots and browser/commit metadata.
3. **CPU-throttled benchmark:** use the same exact build and deterministic fixture at normal CPU and fixed 4x CPU slowdown. Measure initial render, 1,000-row scanner filter/sort/page transition, and chart render with Performance traces and User Timing marks. Repeat each scenario at least five times and report median and p95, plus the raw traces. Do not compare runs with different browser versions, fixtures, cache state or machine profiles.

### Gate and acceptance evidence

These three tests remain **BLOCKED / NOT RUN** until an isolated feature-branch runtime and an executable browser profiling environment are available. The GitHub Actions runner/budget issue must also be cleared before CI-based measurements can be trusted. The reports must identify the exact tested commit and include raw artifacts; no performance pass/fail threshold or improvement claim is assigned without measured data.

Screen-reader testing, physical mobile-device QA and live backend fault testing remain outstanding. The existing automated axe-core result is limited to the initial visible dashboard state and is not a substitute for a screen-reader session.

### Change-control confirmation

This checkpoint is documentation-only. No dashboard application code, backend code, workflow, database, secrets, billing settings, `main`, PR merge state, staging service or production service was changed. No merge/rebase or deployment was performed.


## 33. Isolated performance QA harness added (2026-11-15)

Added a dedicated, feature-branch-only GitHub Actions workflow and local static-server/profiling harness:

- `.github/workflows/dashboard-performance-qa.yml`: manual dispatch and scoped feature-branch push triggers; read-only repository permissions; Ubuntu 24.04; pinned Playwright 1.56.1 and Lighthouse 12.8.2; 25-minute job timeout; artifact upload on success or failure.
- `tests/serve_dashboard_qa.cjs`: serves only the checked-out `dashboard/` directory on loopback port 4173, rejects path traversal, and uses no backend credentials or external service.
- `tests/dashboard_performance_qa.cjs`: runs Chromium at 390×844 with CPU throttle rates 1× and 4×, records initial navigation and up to 12 navigation interaction durations, captures JS heap metrics and DOM node count, and writes V8 heap snapshots plus JSON metadata.

The workflow requests three mobile Lighthouse cold-load JSON reports and preserves raw Lighthouse reports, heap snapshots and browser profile JSON as a 14-day Actions artifact. The isolated dashboard is static and does not connect to a live backend, database, secrets or production.

**Execution status:** harness and workflow files were committed to the feature branch and read back from GitHub. No completed Actions run or uploaded performance artifact has yet been verified in this audit. Therefore Lighthouse scores, Core Web Vitals, heap values and CPU-throttled timings remain **NOT MEASURED / PENDING RUN**. The workflow's successful completion and artifact contents must be checked before publishing any numbers. The current browser harness reports JS heap metrics after interaction/GC and captures snapshots at each CPU rate; it is not a repeated-cycle leak certification or physical-device profile.

No `main` change, merge/rebase, PR merge, staging/production deployment, backend mutation, database change or secret change was made.



## 34. Mobile navigation profiler correction (2026-11-15)

A source review of the new CPU/heap profiling harness found that the dashboard intentionally makes the mobile sidebar inert while it is closed. The first profiler revision attempted to click sidebar links without opening the mobile menu, so its navigation-interaction loop was not reliable at the configured 390px viewport.

Corrected `tests/dashboard_performance_qa.cjs` on the feature branch:
- Open the mobile menu before each navigation-link click when the menu control is visible.
- Wait for the expected hash route after each click, rather than merely waiting for a non-empty breadcrumb.
- Record whether the sidebar is closed after navigation.

Commits:
- `832977e0e8b0cf65ad228d5f27425258222b6434` — mobile menu interaction.
- `61f9cde26c8e78a89a84a4f95e1b762d87df0b8c` — route-completion assertion.

**Verification limit:** these are source-level harness corrections only. The profiler and GitHub Actions workflow have not yet produced a verified completed run or raw artifact in this audit. No navigation timing, Lighthouse score, heap result, or CPU benchmark is claimed.

No application code, backend, database, secrets, `main`, PR merge state, staging or production deployment was changed.


## 35. Performance workflow server-lifecycle fix (2026-11-15)

The first real GitHub Actions execution exposed a workflow orchestration defect. Run #3 (`43723154352`, commit `f981683c31527a566c2ed2985b43eaa9b05fa86f`) successfully installed Playwright/Lighthouse, installed Chromium, and passed the initial static-server readiness step. Lighthouse then failed navigation to `http://127.0.0.1:4173/` with `net::ERR_ABORTED` / `FAILED_DOCUMENT_REQUEST`; the CPU/heap profiling step was skipped. The artifact-upload step did succeed, but its 17,131-byte archive contains only the partial first Lighthouse JSON output and is not valid performance evidence.

**Root cause:** the workflow launched the static server in a separate GitHub Actions step. The runner cleans up background/orphan processes at step boundaries, so the server was no longer available to the following Lighthouse step. This was a workflow process-lifetime error, not an application defect.

Corrected `.github/workflows/dashboard-performance-qa.yml` in commit `12d20a1e083fb631a9ea352d9ba0745b849faf91`:
- Lighthouse step now starts its own loopback-only static server, checks readiness, runs all three samples while the server remains alive, then terminates it with an EXIT trap.
- CPU/heap profiling step independently starts and checks its own static server, runs the profiler within the same shell step, then cleans up.
- No server process is expected to persist across Actions step boundaries.

Run #5 (`43723376649`) for the prior mobile-navigation correction was observed in progress at the time of inspection; its final result is not assumed. The workflow change above triggers a new feature-branch push run. That new run must complete and its logs/artifact must be inspected before any benchmark is considered measured.

No Lighthouse score, Core Web Vitals, CPU timing or heap result is claimed from the failed run. No dashboard application, backend, database, secrets, `main`, PR merge state, staging or production deployment was changed.


## 36. Lighthouse failure isolation and profiler continuity (2026-11-15)

The follow-up run #6 (`43723605988`, workflow commit `12d20a1e083fb631a9ea352d9ba0745b849faf91`) still failed during the first Lighthouse navigation with `net::ERR_ABORTED` / `FAILED_DOCUMENT_REQUEST`. The workflow now kept the static server in the same step as Lighthouse, so the original cross-step process cleanup issue was not sufficient to explain this second failure. The available log does not yet establish the underlying Chrome navigation cause. The run's artifact (`dashboard-performance-12d20a1e083fb631a9ea352d9ba0745b849faf91`, 16.8 KB) contains partial Lighthouse output only; CPU/heap profiling was skipped.

A second workflow adjustment was committed as `eae6aa7ed4c0da7e36b82b8fe20691bd0a150c87`:
- Add explicit Chrome flags to disable proxy use and shared-memory pressure for loopback browser runs.
- Mark Lighthouse as a separately tracked step and allow the CPU/heap profiler to run even if Lighthouse fails.
- Preserve a failed overall job conclusion when Lighthouse fails, while still attempting profiling and artifact upload.

This is a diagnostic/continuity correction, not a performance pass. The exact Lighthouse failure cause remains **unconfirmed** until the next run's Chrome and server logs are inspected. No benchmark metrics are accepted from either failed run.

No application or backend source, database, secrets, `main`, PR merge state, staging or production deployment was changed.


## 37. Static server MIME root-cause correction (2026-11-15)

Run #7 (`43723851624`, workflow commit `eae6aa7ed4c0da7e36b82b8fe20691bd0a150c87`) provided the decisive profiler error: Playwright reported `page.goto: Download is starting` for the dashboard root URL. Inspection of `tests/serve_dashboard_qa.cjs` showed that the root path correctly read `dashboard/index.html`, but computed the response MIME type from `target`, which is the dashboard directory itself for `/`. Because that directory has no `.html` extension, the server returned `application/octet-stream`; Chromium treated the document as a download instead of rendering it. This also explains Lighthouse's earlier `ERR_ABORTED` / `FAILED_DOCUMENT_REQUEST` messages. The prior proxy hypothesis was not the root cause.

Corrected in commit `e996f38583a8edabbae7c9939532430077dd527e`:
- Determine MIME type from the actual served file path (`index.html` for `/`).
- Add `X-Content-Type-Options: nosniff`.

Added a profiler preflight in commit `8bc9b1e993f327a2159726301a423674c3927208`:
- Require a successful root response with `text/html` content type.
- Wait for the visible application shell before recording timings.

Run #7's Lighthouse step exited 1 and produced only partial JSON with `FAILED_DOCUMENT_REQUEST`; its CPU/heap step then failed at initial navigation because of the MIME issue. Its artifact is not valid performance evidence. The MIME fix and preflight now need a fresh workflow run; no score or memory/timing result is claimed yet.

No dashboard application UI, backend business logic, database, secrets, `main`, PR merge state, staging or production deployment was changed.


## 38. QA harness syntax correction (2026-11-15)

The first commits implementing the MIME/preflight fix contained literal escaped newline sequences in the two Node.js scripts. Run #9 (`43724280699`) therefore failed at JavaScript parsing with `SyntaxError: Invalid or unexpected token` in both the Lighthouse server and profiler setup. This was a QA harness syntax error, not a dashboard application failure.

Corrected the line breaks in:
- `tests/serve_dashboard_qa.cjs` — commit `405c4e648dbe18ae7a42887beb15511d230854d8`.
- `tests/dashboard_performance_qa.cjs` — commits `1fdd0effef6d48f10d0b68064d1a171a8fcd336e` and `68b10164b6440960e21370a4a28afb3d3bce28d4` (final profiler correction).

The latest commit should trigger a fresh workflow run. The scripts were re-read from the feature branch after correction. No runtime pass is claimed until the new Actions run executes.


## 39. First successful Lighthouse + CPU/heap profiling run (2026-11-15)

**Run #12 succeeded:** [GitHub Actions run 43724640678](https://github.com/mamunfb/universal-binance-ai-backend/actions/runs/43724640678), commit `68b10164b6440960e21370a4a28afb3d3bce28d4`. All workflow steps passed: dependency setup, Chromium install, three Lighthouse cold loads, CPU-throttled browser/heap profiling, and artifact upload.

Artifact: `dashboard-performance-68b10164b6440960e21370a4a28afb3d3bce28d4` (1,762,647 bytes; retained until 2026-11-29). It contains three Lighthouse JSON reports, a browser profile JSON, and 1x/4x V8 heap snapshots.

### Lighthouse mobile results

Test configuration: isolated static feature-branch dashboard, Chromium 141, 390 × 844 CSS-pixel viewport, Lighthouse mobile simulated throttling, three cold-load samples.

| Metric | Sample 1 | Sample 2 | Sample 3 | Median |
|---|---:|---:|---:|---:|
| Performance score | 97 | 100 | 100 | 100 |
| FCP | 907 ms | 903 ms | 902 ms | 903 ms |
| LCP | 1,785 ms | 1,653 ms | 1,502 ms | 1,653 ms |
| Speed Index | 907 ms | 903 ms | 902 ms | 903 ms |
| Total Blocking Time | 191 ms | 0 ms | 0 ms | 0 ms |
| CLS | 0.0000238 | 0.0000238 | 0.0000238 | 0.0000238 |

TBT varied between the first and later samples; retain all three samples rather than treating the median as a guarantee. CLS is very close to zero in this lab run. INP is not established by these Lighthouse cold-load samples and is not claimed.

### CPU-throttled browser navigation + heap observations

Test configuration: Chromium 141, 390 × 844 viewport, 12 in-app navigation clicks per run, CPU throttle set to 1x and 4x.

| Observation | 1x | 4x |
|---|---:|---:|
| Initial DOMContentLoaded navigation | 54 ms | 59 ms |
| In-app navigation median | 151 ms | 306 ms |
| In-app navigation p95 (12 samples, nearest rank) | 295 ms | 333 ms |
| Heap used after forced GC | 1,921,260 bytes | 1,921,340 bytes |
| Heap total | 2,957,312 bytes | 2,957,312 bytes |
| DOM nodes | 1,243 | 1,243 |
| Browser page errors | 0 | 0 |
| Mobile sidebar closed after each click | 12/12 | 12/12 |

Heap snapshots were captured after the navigation sequence and forced garbage collection. The nearly identical post-GC heap observations are encouraging but do **not** establish absence of memory leaks: there is no before/after repeated-cycle retained-heap comparison yet. The 12-navigation run is a navigation smoke benchmark, not the 1,000-row scanner stress benchmark.

### Scope and limitations

- These are CI lab measurements for the isolated static dashboard, not production field Core Web Vitals or real-user INP.
- The browser profiler did not populate 1,000 scanner rows; no 1,000-row render timing is claimed here.
- No repeated-cycle heap-growth trend or detached-DOM leak certification is claimed.
- Screen-reader/manual assistive-technology QA and physical-device mobile QA remain outstanding.
- No live backend fault testing was performed; the harness intentionally runs without backend credentials or external services.

This is the first accepted performance evidence in this audit. Continue with deterministic 1,000-row scanner fixture timing, repeated interaction/cleanup heap comparisons, and manual accessibility/mobile verification before declaring the dashboard fully performance- or accessibility-certified.


## 40. Deterministic 1,000-row scanner benchmark harness (2026-11-15)

Extended `tests/dashboard_performance_qa.cjs` in commit `6bee57edfe9f4d11ef77ff389d9afb43025330df` to exercise the real dashboard scanner UI with a deterministic, browser-intercepted 1,000-row fixture. The fixture is isolated to `https://qa.invalid` routes intercepted by Playwright; no live backend, API credentials, Binance endpoint, or production service is contacted.

For each CPU setting (1x and 4x), the harness now:
- Applies the mock backend URL through the dashboard Settings UI and verifies the mocked health response.
- Runs the real Spot Scanner UI against 1,000 synthetic row objects.
- Records scan-to-visible-rows, sort, search, and pagination timings and visible row counts.
- Repeats five search/clear/sort/page-forward/page-back cycles.
- Forces garbage collection and captures baseline and post-cycle heap metrics/snapshots for comparison.

Run #13 (`43725367464`, commit `6bee57edfe9f4d11ef77ff389d9afb43025330df`) was still in progress at the latest inspection; Chromium installation was ongoing and no fixture benchmark result is available yet. Do not infer a pass from the earlier Run #12, which predates this expanded fixture.


## 41. Run #13 scanner-fixture timeout and diagnostic follow-up (2026-11-15)

Run #13 (`43725367464`, commit `6bee57edfe9f4d11ef77ff389d9afb43025330df`) completed with failure. The three Lighthouse cold-load audits passed. The expanded CPU/heap profiler failed at the assertion waiting for `#spot-count` to become `1000 matching / 1000 returned`; the wait timed out after 30 seconds. Therefore Run #13 provides no accepted 1,000-row timing or repeated-cycle heap comparison. The artifact upload succeeded, but it contains only the Lighthouse reports because the profiler exited before producing its profiling output.

Added targeted failure diagnostics in commit `e44a79be840954e120031b337616bc450edb56ec`: capture mocked API response/request failures, browser page errors, scanner state, count, coverage, toast, button state, settings status, and route hash when the fixture does not render. The next run will distinguish a missing click/event, a failed/mismatched mock request, an API/schema issue, and a dashboard rendering issue instead of reporting only a generic timeout.

No dashboard application source or backend code changed. No live backend calls, database/secrets changes, `main` changes, merges, or deployments.



## 42. Run #14 scanner assertion diagnosis (2026-11-15)

Run #14 ([workflow 43726195766](https://github.com/mamunfb/universal-binance-ai-backend/actions/runs/43726195766), profiler job 132848540298) completed with failure. Chromium setup and all three mobile Lighthouse cold-load audits passed. The profiler reached the Spot Scanner and the deterministic mock API returned HTTP 200 for both `/health` and `/api/v1/markets/spot/scan`.

The captured browser diagnostics establish that the dashboard successfully rendered the fixture:
- Scanner state: `ok`
- Displayed count: `1,000 matching / 1,000 returned`
- Coverage: 1,000 returned rows, 1,000 unique symbols, zero duplicate or malformed rows
- Fixture source: `deterministic QA fixture`
- Browser page errors: zero

The assertion expected the unformatted literal `1000 matching / 1000 returned`, while the dashboard correctly formats counts with locale grouping separators. In addition, the original Playwright `waitForFunction` options argument was passed in the argument position, so the intended 10-second timeout was not applied; the actual wait timed out after 30 seconds. This was a test assertion/configuration defect, not a dashboard data-loading defect.

Run #14 artifact uploaded successfully (artifact ID `14166491931`, 214,298 bytes), but it contains only the three Lighthouse JSON reports; no scanner timings or heap snapshots were produced. No 1,000-row performance metrics are claimed from this run.

## 43. Locale-aware scanner assertions and Run #16 (2026-11-15)

Updated `tests/dashboard_performance_qa.cjs` to remove comma grouping from displayed scanner counts before comparing them with expected numeric text, covering initial render, search, clearing search, and all five repeated interaction cycles. Corrected the initial wait to pass Playwright's options in the third argument position, so the 10-second diagnostic timeout is now effective.

Changes were committed on `feat/institutional-dashboard-design`:
- `144e34e09b56d308cf3d1b5e7cb4cac87ecd45f5` — initial locale-aware assertion update.
- `3fd5c762384d91053b531e28f386be00278f1ea7` — completed normalization of all remaining repeated-cycle assertions.

Run #16 ([workflow 43726505493](https://github.com/mamunfb/universal-binance-ai-backend/actions/runs/43726505493)) was observed running against commit `3fd5c762384d91053b531e28f386be00278f1ea7`. At the time of this audit update, Chromium installation was still in progress; no profiler pass or 1,000-row timing/heap result is claimed yet.

Scope remains unchanged: no dashboard application logic, backend, database, secrets, `main`, PR merge state, staging, or production deployment was modified.



## 44. Run #16 pager selector diagnosis and correction (2026-11-15)

Run #16 ([workflow 43726505493](https://github.com/mamunfb/universal-binance-ai-backend/actions/runs/43726505493), job 132849512315) completed with failure. All three Lighthouse cold-load audits passed. The locale-aware scanner count assertion no longer failed; the profiler advanced beyond the initial 1,000-row scan and sort to the pagination step.

The next failure was a Playwright strict-mode selector error: the generic `.table-pager button[aria-label="Next scanner page"]` matched three scanner page sections (Spot, USDⓈ-M, and COIN-M) simultaneously. The test must target only the active Spot Scanner page. No dashboard UI defect is indicated by this failure.

Corrected all Next/Previous pager selectors in `tests/dashboard_performance_qa.cjs` to scope them under `#page-spot-scanner`. Commit: `8da9dc9b193767fd7deb2877a7619dcee4038408`.

Run #16 artifact `14166841719` contains only the three Lighthouse JSON reports (213,091 bytes); the profiler stopped at the ambiguous pager selector, so no completed 1,000-row timings or heap snapshots are available from this run.

## 45. Run #17 after pager selector correction (2026-11-15)

Run #17 ([workflow 43726789990](https://github.com/mamunfb/universal-binance-ai-backend/actions/runs/43726789990)) was observed running on branch `feat/institutional-dashboard-design`, commit `8da9dc9b193767fd7deb2877a7619dcee4038408`. Chromium installation passed and the three-sample mobile Lighthouse stage was in progress at the time of this update. CPU/heap profiling has not yet started; no new scanner performance or heap result is claimed.

No dashboard application source, backend business logic, database, secrets, `main`, PR merge state, staging or production deployment was changed.


## 46. Run #17 successful 1,000-row benchmark and Lighthouse evidence (2026-11-15)

Run #17 ([workflow 43726789990](https://github.com/mamunfb/universal-binance-ai-backend/actions/runs/43726789990), job 132850355237) completed successfully on `feat/institutional-dashboard-design`, commit `8da9dc9b193767fd7deb2877a7619dcee4038408`. Chromium setup, all three Lighthouse mobile cold-load runs, CPU-throttled browser/heap profiling, and artifact upload succeeded. The profiler output confirms that the Spot Scanner accepted and rendered the full deterministic 1,000-row fixture; this is the first completed scanner fixture benchmark in this audit.

### Lighthouse mobile cold-load results

Artifact JSON files were downloaded and inspected directly. Test viewport: 390 × 844 CSS px; Lighthouse mobile simulated throttling; three cold-load samples.

| Metric | Sample 1 | Sample 2 | Sample 3 | Median |
|---|---:|---:|---:|---:|
| Performance score | 100 | 100 | 100 | 100 |
| FCP | 904 ms | 903 ms | 902 ms | 903 ms |
| LCP | 1,535 ms | 1,653 ms | 1,693 ms | 1,653 ms |
| Speed Index | 904 ms | 903 ms | 902 ms | 903 ms |
| Total Blocking Time | 0 ms | 0 ms | 0 ms | 0 ms |
| CLS | 0.0000238 | 0.0000238 | 0 | 0.0000238 |

The Lighthouse CLI also logged non-fatal Lantern diagnostics that the all-frames FCP/LCP computations are not implemented; each report was nevertheless generated and the Lighthouse command completed successfully. The reported core page metrics above are read from the actual JSON reports. These are isolated static-dashboard lab measurements, not production field data or a real-user INP result.

### Deterministic 1,000-row Spot Scanner fixture

The Playwright harness intercepted the mock API on `qa.invalid`; no live Binance endpoint, backend credentials, or production service was used. The real dashboard Settings and Spot Scanner UI paths were exercised.

| Measurement | CPU 1x | CPU 4x |
|---|---:|---:|
| 1,000-row scan render | 67 ms | 93 ms |
| Sort | 37 ms | 74 ms |
| Search | 156 ms | 177 ms |
| Search result rows | 1 | 1 |
| Pagination | 68 ms | 120 ms |
| Five repeated search/clear/sort/next/previous cycles | 2,351 ms | 2,975 ms |
| Heap before repeated cycles | 2,320,812 bytes | 2,315,908 bytes |
| Heap after repeated cycles | 2,413,072 bytes | 2,373,340 bytes |
| Heap delta | +92,260 bytes | +57,432 bytes |
| DOM nodes after cycles | 2,662 | 2,659 |
| Browser page errors | 0 | 0 |

The first page displayed 100 rows from the 1,000-row fixture. Twelve in-app route navigations also completed with the mobile sidebar closed after every click (12/12 at both CPU settings); route-navigation median was 149 ms at 1x and 270 ms at 4x. Initial navigation was 32 ms / 52 ms respectively.

Heap snapshots were captured at baseline and after the five interaction cycles for both CPU settings. The measured post-GC heap deltas are limited observations from this specific fixture/run; they do not certify the absence of memory leaks or detached-DOM retention. A longer repeated soak test and snapshot-retainer comparison remain appropriate follow-up work.

### Evidence and scope

- Artifact: [dashboard-performance-8da9dc9b193767fd7deb2877a7619dcee4038408](https://github.com/mamunfb/universal-binance-ai-backend/actions/runs/43726789990/artifacts/14166732415)
- Artifact ID: `14166732415`; 4,764,528 bytes; SHA-256 `de3711bac0d3fe12572d7b83c8d7a6ce73f2e0a6210de77a56fd8c7799bc0d58`.
- Contents inspected: three Lighthouse JSON reports, browser profile JSON, and four baseline/after-cycle V8 heap snapshots.
- No dashboard application source, backend logic, database, secrets, `main`, PR merge state, staging, or production deployment was changed by this benchmark/audit update.
- Physical-device mobile testing, manual keyboard/screen-reader verification, and a longer memory soak/leak investigation remain outstanding. Do not describe the dashboard as fully production-certified on the basis of this CI lab run.


## 47. Heap benchmark DOM-settling guard (2026-11-15)

Review of the Run #17 V8 heap snapshots found that the baseline snapshot was taken after the scanner count label returned to 1,000 matching rows, but the harness did not separately wait for all 100 visible table rows to be restored before taking that snapshot. The after-cycle snapshot followed pagination waits and contained the expected full 100-row page. This means the Run #17 heap deltas (+92,260 bytes at 1x and +57,432 bytes at 4x) may include DOM row restoration/lazy rendering rather than only retained growth across repeated cycles; they must be treated as provisional and not as a memory-leak signal or a clean like-for-like comparison.

Updated `tests/dashboard_performance_qa.cjs` on the feature branch to wait explicitly for exactly 100 visible `#spot-rows tr` elements after clearing the search before baseline garbage collection/snapshot, and after each repeated-cycle search clear. The final cycle already waits for page 1/10; the explicit row-count guard makes the intended DOM state measurable at both comparison points.

This is a test-harness reliability correction only. It does not alter dashboard application code or backend behavior. A fresh Run #18 is required before publishing a corrected heap delta. Until that run completes, the Run #17 scanner timings remain valid as recorded, but its heap delta remains provisional. No claim of leak absence is made.


## 48. Heap snapshot wrapper-materialization follow-up (2026-11-15)

After Run #18 passed with the 100-row count guard, direct inspection of the V8 snapshots showed 24 `HTMLTableCellElement` wrapper objects in each baseline snapshot versus 624 after the five interaction cycles. The 100-row DOM count guard alone therefore did not prove that equivalent cell wrappers had been materialized at both snapshot points. This can make the measured heap delta include lazy wrapper materialization and still prevents a clean retained-heap comparison.

Strengthened `tests/dashboard_performance_qa.cjs` again in commit `d6b28aae08b5ea9c5f3fa8fba03f75a8ec4774ff`: before the baseline snapshot and after each search-clear cycle, the harness now explicitly traverses every visible table cell, reads its text, forces layout with `getBoundingClientRect()`, and asserts exactly 100 rows / 600 cells. This aims to make wrapper materialization consistent before comparing snapshots.

Run #18 remains a successful execution of the earlier row-count guard, but its heap delta is still provisional because of the wrapper-count discrepancy found in the downloaded artifact. The new cell-materialization guard requires a fresh CI run before any updated heap interpretation. This is QA harness-only; no dashboard application, backend, database, secrets, `main`, merge state, or deployment was changed.


## 49. Heap snapshot strong-reference normalization (2026-11-15)

Run #19 ([workflow 43727872396](https://github.com/mamunfb/universal-binance-ai-backend/actions/runs/43727872396)) passed with the explicit 100-row / 600-cell traversal guard. However, after downloading and inspecting its V8 snapshots, the baseline still contained only 24 `HTMLTableCellElement` JS wrappers while the post-cycle snapshot contained 624. The page had 100 rows and the traversal accessed all 600 cells, but wrappers created during traversal were not strongly retained after the evaluation returned. Thus the baseline/post-cycle snapshot wrapper populations were still not comparable.

Updated the test-only `settleScannerDom` helper in commit `0d740892d1463bc1fd125fc25992d4edd782cbde` to keep the current 600 cell wrapper references in `window.__qaHeapKeepAlive` through each snapshot and assert all 600 remain connected. The helper refreshes this reference array after each clear/search cycle, so references to replaced rows are not intentionally retained between cycles. This should produce equivalent wrapper populations in the baseline and final snapshots; the next CI artifact must be inspected to confirm rather than assumed.

Run #19 scanner interaction timings remain valid as observations: 1x render/sort/search/pagination 66/38/170/69 ms, five cycles 2,406 ms; 4x 86/79/171/128 ms, five cycles 3,349 ms. The measured heap deltas (+61,636 / +49,752 bytes) remain provisional until snapshot wrapper counts are verified as comparable. No dashboard application or backend source changed.


## 50. Run #20 strong-reference experiment and evidence review (2026-11-15)

Run #20 ([workflow 43728309911](https://github.com/mamunfb/universal-binance-ai-backend/actions/runs/43728309911)) completed successfully on commit `0d740892d1463bc1fd125fc25992d4edd782cbde`. All workflow steps passed, including three Lighthouse mobile audits, CPU-throttled profiling, and artifact upload. The profiler exercised the full 1,000-row mock Spot Scanner fixture and reported no browser page errors.

### Scanner interaction timings

| Measurement | CPU 1x | CPU 4x |
|---|---:|---:|
| Scan render | 67 ms | 92 ms |
| Sort | 38 ms | 80 ms |
| Search | 170 ms | 179 ms |
| Pagination | 68 ms | 130 ms |
| Five repeated interaction cycles | 2,350 ms | 3,127 ms |
| Browser page errors | 0 | 0 |

### Lighthouse mobile results

Three cold-load samples, 390 × 844 viewport, mobile simulated throttling. Values are read from the uploaded Lighthouse JSON reports.

| Metric | Sample 1 | Sample 2 | Sample 3 | Median |
|---|---:|---:|---:|---:|
| Performance score | 97 | 100 | 100 | 100 |
| FCP | 1,579 ms | 903 ms | 903 ms | 903 ms |
| LCP | 1,879 ms | 1,653 ms | 1,653 ms | 1,653 ms |
| Speed Index | 1,579 ms | 903 ms | 903 ms | 903 ms |
| Total Blocking Time | 176 ms | 0 ms | 0 ms | 0 ms |
| CLS | 0 | 0.0000238 | 0.0000238 | 0.0000238 |

The first Lighthouse sample is slower than the subsequent two; retain all three samples and do not treat the median as a guarantee.

### Heap snapshot interpretation remains unresolved

The strong-reference experiment in commit `0d740892d1463bc1fd125fc25992d4edd782cbde` was intended to keep 600 cell wrappers alive at both snapshot points. Direct inspection of the resulting artifact still found 24 `HTMLTableCellElement` wrapper objects in each baseline snapshot and 1,224 after-cycle, while the browser profiler's DOM-node metric rose to 3,962 / 3,959. This confirms that the artificial keep-alive approach changed snapshot retention and did not create a comparable baseline/post-cycle heap population.

Consequently, the reported heap deltas (+80,092 bytes at 1x and +81,224 bytes at 4x) are **not valid evidence of application memory growth or leak behavior**. The V8 snapshots are retained for further inspection, but no leak/no-leak conclusion is made. Future memory work should use a dedicated harness that measures stable app-owned objects without pinning transient DOM wrappers, or should omit numerical heap-delta claims and rely on targeted retained-object/retainer analysis.

Artifact: [dashboard-performance-0d740892d1463bc1fd125fc25992d4edd782cbde](https://github.com/mamunfb/universal-binance-ai-backend/actions/runs/43728309911/artifacts/14167611050), artifact ID `14167611050`, 4,872,138 bytes, SHA-256 `f85e30d715df50cf7bb6dff2f39b4bab07dad48dc3b7e5a19c6226e8eaf2a861`.

No dashboard application source, backend logic, database, secrets, `main`, PR merge state, staging, or production deployment was changed by this run or its audit entry.


## 51. Heap snapshot retention root cause isolated; refresh keep-alive after pagination (2026-11-15)

Inspected all four V8 heap snapshots from Run #20 (artifact `14167611050`) directly. The baseline snapshots contained 18 `HTMLTableRowElement` and 31 `HTMLTableCellElement` wrapper nodes; the after-cycle snapshots contained 218 row wrappers and 1,231 cell wrappers. This explains why the strong-reference normalization had not worked: `settleScannerDom()` refreshed `window.__qaHeapKeepAlive` immediately after clearing search, but each cycle then sorted and paginated the table, replacing the rows. The global keep-alive array consequently retained the pre-pagination rows while the final DOM contained a different page-1 row set. Five cycles accumulated detached row/cell wrappers through this test-only reference.

Corrected `tests/dashboard_performance_qa.cjs` in commit `4be281754c38d38003705e357a7d55fa917be6a1` to call `settleScannerDom()` again after the Previous-page action returns to page 1 at the end of every repeated cycle. This refreshes the strong references to the final live page rows, replacing references to the rows detached by sort/pagination before the final garbage collection and snapshot.

This is a profiler-harness correction, not evidence of a dashboard application memory leak. Run #20 heap deltas remain invalid for leak interpretation. A new CI artifact must be downloaded and its baseline/after-cycle row and cell wrapper counts compared before any heap conclusion is published.


## 52. Replace unstable V8 snapshot comparison with matched post-GC metrics (2026-11-15)

Run #21 ([workflow 43731845974](https://github.com/mamunfb/universal-binance-ai-backend/actions/runs/43731845974)) passed on commit `4be281754c38d38003705e357a7d55fa917be6a1`, but direct inspection of its artifact showed the baseline and after-cycle V8 snapshots still did not contain comparable JavaScript DOM-wrapper populations. In both baseline snapshots, 600 native `<td>` elements were present, but only 24 `HTMLTableCellElement` JS wrappers were represented; after five cycles, 624 wrappers were represented. The keep-alive array itself retained the current native cells, but snapshot wrapper materialization still differed. This makes V8 object-count comparisons and their heap deltas unsuitable as leak evidence.

To avoid manufacturing misleading snapshot evidence, commit `ebf7e8849bd0ef71a1ff510b34f64884af839ce7` removes the baseline/after-cycle V8 snapshot captures and the global DOM keep-alive array. The harness now:
- asserts a stable 100-row / 600-cell scanner DOM before GC metrics;
- records `Performance.getMetrics` after explicit garbage collection at the baseline and after five interaction cycles;
- restores the same quote-volume ascending sort and page-1 state before the final GC metric;
- labels the difference `gc_heap_delta_bytes`, not a leak measurement.

This is a coarse post-GC heap/DOM trend for the deterministic mock fixture only. It does not prove absence or presence of a leak; no numerical leak threshold is asserted. The next CI artifact must be checked to confirm the final state and metrics. The workflow should no longer emit V8 heap snapshots. Scanner interaction timing remains independently measured.

Run #21 results from its profiler output: 1x scan render/sort/search/pagination 67/38/170/68 ms; 4x 86/79/171/130 ms; five cycles 2,350 ms at 1x and 3,127 ms at 4x. These timing observations are from a deterministic 1,000-row mocked response, not production traffic.


## 53. Run #22 matched-GC profiler verification (2026-11-15)

Run #22 ([workflow 43732332892](https://github.com/mamunfb/universal-binance-ai-backend/actions/runs/43732332892)) completed successfully on commit `ebf7e8849bd0ef71a1ff510b34f64884af839ce7`. The profiler step and artifact upload passed. The new artifact (ID `14169365473`, 226,254 bytes, SHA-256 `a299da2f248fa616906ce976372a556c5140fbbdd24f3c9c77a7c28b884a59ae`) contains three Lighthouse JSON reports and `browser-profile.json`; it no longer contains V8 heap snapshots.

### 1,000-row scanner fixture

| Measurement | CPU 1x | CPU 4x |
|---|---:|---:|
| Scan render | 66 ms | 98 ms |
| Sort | 38 ms | 81 ms |
| Search | 171 ms | 189 ms |
| Pagination | 69 ms | 140 ms |
| Five repeated interaction cycles | 2,449 ms | 3,303 ms |
| Post-GC heap delta (raw trend only) | +71,824 bytes | +71,824 bytes |
| DOM nodes after cycles | 2,652 | 2,649 |
| Browser page errors | 0 | 0 |

The harness restores the same ascending sort and page-1 state before the final GC measurement. These heap deltas are coarse lab observations only; the harness does not assert a memory-leak threshold and the values do not establish a leak or its absence. The DOM node counts are reported after cycles; baseline DOM-node count was not included in this run's output and will be added in a follow-up for a more useful before/after comparison.

### Lighthouse mobile cold-load

Three samples, 390 × 844 CSS px, mobile simulated throttling; values read directly from the artifact JSON.

| Metric | Sample 1 | Sample 2 | Sample 3 | Median |
|---|---:|---:|---:|---:|
| Performance score | 99 | 100 | 100 | 100 |
| FCP | 904 ms | 903 ms | 906 ms | 904 ms |
| LCP | 1,656 ms | 1,653 ms | 1,506 ms | 1,653 ms |
| Speed Index | 904 ms | 903 ms | 906 ms | 904 ms |
| Total Blocking Time | 72 ms | 0 ms | 0 ms | 0 ms |
| CLS | 0.0000238 | 0.0000238 | 0.0000238 | 0.0000238 |

The artifact confirms the profiler output and Lighthouse reports; these remain isolated static-dashboard lab measurements using a deterministic mock scanner API, not live Binance or production-user performance.


## 54. Run #23 browser keyboard regression and matched-GC baseline DOM results (2026-11-15)

Two independent feature-branch workflows completed successfully:

- Dashboard browser QA: [Run 43733156900](https://github.com/mamunfb/universal-binance-ai-backend/actions/runs/43733156900), commit `d528e481cf08b477eb1c02894de8afac79b2003f`.
- Dashboard performance QA: [Run 43733165359](https://github.com/mamunfb/universal-binance-ai-backend/actions/runs/43733165359), commit `7a9e9c27ab60fb3733c440d7653ec675db16b396`.

### Browser regression tests

The Chromium browser suite completed with **10 passed, 0 failed** (14.18 seconds). The 1,000-row mobile scanner test now additionally verifies:
- Enter and Space both activate the focused sortable table header and update sort order;
- pagination restores focus to the corresponding Next/Previous control after the table rerenders;
- Enter and Space keyboard activation work across page changes;
- existing 360–1280px responsive, sidebar focus-trap/Escape, API failure, timeout/cancellation, reduced-motion, and automated axe accessibility checks remain in the same passing suite.

This is automated Chromium/axe evidence, not a manual screen-reader or physical-device audit.

### Performance QA: scanner and memory trend

The performance workflow passed all steps and uploaded artifact `14169074007` (227,043 bytes; SHA-256 `400af5c7b0d9808b529d675636c4a84971e6e4d20445dd936c831846b0942f1a`). The artifact contains three Lighthouse reports and browser-profile JSON; no V8 snapshots are produced.

| Measurement | CPU 1x | CPU 4x |
|---|---:|---:|
| Scan render | 68 ms | 90 ms |
| Sort | 36 ms | 82 ms |
| Search | 156 ms | 179 ms |
| Pagination | 69 ms | 123 ms |
| Five repeated cycles | 2,353 ms | 3,067 ms |
| Post-GC heap delta | +35,620 bytes | +71,876 bytes |
| DOM nodes before cycles | 2,647 | 2,647 |
| DOM nodes after cycles | 2,652 | 2,652 |
| DOM node delta | +5 | +5 |
| Browser page errors | 0 | 0 |

The DOM-node count remained close to the baseline (+5) after the five-cycle fixture run. Post-GC heap deltas are still coarse observations only and are not a leak/no-leak verdict.

### Lighthouse mobile cold-load

Three samples at 390 × 844 CSS px with Lighthouse mobile simulated throttling; values read from the uploaded JSON reports.

| Metric | Sample 1 | Sample 2 | Sample 3 | Median |
|---|---:|---:|---:|---:|
| Performance score | 93 | 100 | 100 | 100 |
| FCP | 1,834 ms | 904 ms | 902 ms | 904 ms |
| LCP | 2,134 ms | 1,654 ms | 1,652 ms | 1,654 ms |
| Speed Index | 1,834 ms | 904 ms | 902 ms | 904 ms |
| Total Blocking Time | 250 ms | 0 ms | 0 ms | 0 ms |
| CLS | 0 | 0.0000238 | 0.0000238 | 0.0000238 |

The first sample is a slower cold-load outlier; retain all samples and do not present the median as a guaranteed user experience. These are isolated static-dashboard lab measurements with a deterministic mocked scanner API, not production-user metrics.

No dashboard application source, backend logic, database, secrets, `main`, PR merge state, staging, or production deployment was changed by these QA-only commits.


## 55. Full backend/Python regression suite and final feature-branch CI verification (2026-11-15)

The push-triggered full test workflow completed successfully on the latest audit commit `04099d2e9176e08639fc122c91780ad6183e6435`:

- [Backend and dashboard tests Run 43733920757](https://github.com/mamunfb/universal-binance-ai-backend/actions/runs/43733920757): **634 passed, 0 failed, 2 warnings** in 3.46 seconds.
- The 2 warnings are deprecation warnings: Starlette's `httpx` TestClient integration and a FastAPI `example` parameter. They did not fail the suite.
- Dashboard HTML/script-reference validation succeeded (2 script references).
- `node --check dashboard/app.js` and `node --check dashboard/chart.js` succeeded.
- The full Python test suite completed successfully.

Together with Run #24 browser QA (10/10 passed) and Run #23 dashboard performance QA (success), the current feature branch has green results across the full Python suite, dashboard browser regression suite, and isolated performance harness.

The 634-test result is from the actual workflow log line: `634 passed, 2 warnings in 3.46s`. No test count is inferred from the workflow summary. The two warnings remain recorded for future dependency/API cleanup; no unrelated package or backend changes were made in this QA pass.

Latest audited commit: `04099d2e9176e08639fc122c91780ad6183e6435`. These checks do not replace physical-device testing, manual assistive-technology review, or production monitoring. No merge, rebase, deployment, `main` modification, backend behavior change, database change, or secrets change was performed.


## 56. Latest full-suite rerun on audit-head commit (2026-11-15)

The audit-only update at commit `58a00dc592109d9ca7da16f65740ca164e13d4fa` triggered another complete Backend and dashboard tests workflow:

- [Run 43734639060](https://github.com/mamunfb/universal-binance-ai-backend/actions/runs/43734639060): completed successfully.
- Python suite: **634 passed, 0 failed, 2 deprecation warnings in 4.72 seconds** (exact final pytest summary from job log).
- Dashboard HTML/script reference validation passed.
- Dashboard JavaScript syntax checks passed for `app.js` and `chart.js`.

This confirms the audit-head commit itself, not only its parent, passed the repository's full push-triggered test workflow. The two known deprecation warnings remain non-fatal and unchanged.


## 57. Final full-suite confirmation on current branch head (2026-11-15)

The final documentation commit `13245e7a18609413519683b122a565bd0f740e0a` was also checked by the push-triggered workflow:

- [Run 43734789232](https://github.com/mamunfb/universal-binance-ai-backend/actions/runs/43734789232): success.
- Exact pytest log: **634 passed, 0 failed, 2 warnings in 4.90 seconds**.
- Dashboard markup/script checks and both JavaScript syntax checks passed.

This confirms that the latest branch-head commit at the time of this entry passed the full test workflow. The warnings are the same two non-fatal deprecation warnings described in section 55. No application code was changed by the documentation-only commits.



## 58. Narrow-mobile responsive viewport regression coverage (2026-11-15)

Expanded the automated responsive-layout test in `tests/test_dashboard_browser.cjs` from seven viewport widths to ten: **320, 344, 360, 390, 480, 760, 768, 900, 1100, and 1280 CSS pixels**. The test checks both document and body scroll widths against the viewport and asserts there are no uncaught browser page errors. This specifically exercises the existing narrow-screen CSS rules below 360px without changing dashboard application CSS or behavior.

The test-only commit is `b2334a35f2c07730ae01ffc3970c2997b482526e` on `feat/institutional-dashboard-design`.

Two independent GitHub Actions workflows completed successfully on that exact commit:

- [Dashboard browser QA Run 43735279472](https://github.com/mamunfb/universal-binance-ai-backend/actions/runs/43735279472): **10 passed, 0 failed, 0 cancelled, 0 skipped**. The responsive viewport test passed at all ten widths; the existing mobile sidebar keyboard/focus, API error/timeout/cancellation, 1,000-row scanner keyboard/pagination, and axe WCAG 2.1 A/AA checks also passed.
- [Backend and dashboard tests Run 43735279349](https://github.com/mamunfb/universal-binance-ai-backend/actions/runs/43735279349): **634 passed, 0 failed, 2 warnings in 4.46 seconds**. Dashboard document/script reference validation and JavaScript syntax checks also passed. The two warnings are the previously documented non-fatal deprecations.

This is Chromium automation on the CI runner, not a physical-device test. Manual screen-reader/assistive-technology verification and production-user performance monitoring remain outstanding. Only the browser test viewport list and this audit document were changed; no dashboard application source, backend logic, database, secrets, `main`, PR merge state, staging, or production deployment was changed.


## 59. API status-class and mobile viewport-transition regression coverage (2026-11-15)

Added two Chromium browser regression cases in `tests/test_dashboard_browser.cjs`:

- API error handling now explicitly exercises HTTP **401, 403, 429 and 500** responses, verifies that backend-provided error details remain visible in the dashboard, and checks that HTML-like error text is rendered as text rather than inserted as markup.
- Mobile navigation now exercises a **390px → 1024px → 390px** viewport transition while a sidebar link owns focus. The test verifies that desktop navigation is not inert, the mobile menu's expanded state is reset, and focus returns to the menu control before the sidebar becomes inert again.

Test-only commit: `08df16665cec566bbad3ee4c4954081b1570428f` on `feat/institutional-dashboard-design`.

**Validation status at documentation time:** GitHub accepted the commit, but a completed CI run/status for this commit was not yet available through the connected GitHub checks. These two new cases are therefore **committed, not yet CI-verified**. Do not interpret earlier successful Chromium runs as validation of these newly added cases.

Physical Android/iPhone testing and manual screen-reader verification remain outstanding. No dashboard application source, backend business logic, database, secrets, `main`, PR metadata, or deployment configuration was changed.

## 60. Mobile accessibility-state and API transport regression coverage (2026-11-15)

Added two additional browser regression cases to `tests/test_dashboard_browser.cjs`:

- Runs axe-core WCAG 2.1 A/AA checks at a 390px mobile viewport with the navigation both closed (inert) and open (keyboard accessible), then verifies Escape returns the sidebar to its inert closed state.
- Verifies API fetch configuration uses `credentials: "omit"` and `cache: "no-store"`, and that a browser cookie scoped to the backend origin is not transmitted with the health request.

Latest test commit: `49a0d374de2513537d292d183635e10ad63bd598`.

**Validation status:** the changes are committed on the feature branch. No completed CI run or local Chromium execution has yet been verified for this commit; these new tests remain pending execution. Earlier CI success does not validate these newly added cases. Physical Android/iPhone testing and manual TalkBack/VoiceOver checks remain outstanding.

No dashboard application source, backend business logic, database, secrets, `main`, PR metadata, or deployment configuration was changed.

## 61. Health-request cancellation and stale-response regression coverage (2026-11-15)

Added a Chromium browser regression case in `tests/test_dashboard_browser.cjs` for clearing backend credentials while a health request is in flight. The test observes the request's AbortSignal, waits for the mocked late response path to settle, and verifies that the cleared-credentials health message, disconnected status, and settings confirmation remain intact rather than being overwritten by stale request state.

Test commit: `b6a203c315331531c16d537b8a570c3e0804802c` on `feat/institutional-dashboard-design`.

**Validation status:** committed to the feature branch. This test has not yet been verified by a completed CI run or local Chromium execution; it remains pending execution. Earlier passing CI runs do not validate this new case. The automated case does not replace physical Android/iPhone testing or manual TalkBack/VoiceOver review.

No dashboard application source, backend business logic, database, secrets, `main`, PR metadata, merge state, or deployment configuration was changed. No merge or deployment was performed.

## 62. Live-region announcement semantics regression coverage (2026-11-15)

Added a Chromium browser assertion for the dashboard's asynchronous status outputs. It verifies that the connection, scan, health, chart, technical-summary, settings, and data-quality status elements retain `role="status"`, `aria-live="polite"`, and `aria-atomic="true"`; transient toast feedback is also checked for a polite live region.

Test commit: `e36843d17972abe667632d84b89036d86fafac7f` on `feat/institutional-dashboard-design`.

**Validation status:** committed; this additional assertion has not yet been verified by a completed CI run or local Chromium execution. Existing axe-core checks and previous successful runs do not establish that this new assertion passed. Manual TalkBack/VoiceOver announcement quality checks remain outstanding.

No dashboard application source, backend business logic, database, secrets, `main`, PR metadata, merge state, or deployment configuration was changed. No merge or deployment was performed.

## 63. Overlapping market-scan stale-response regression coverage (2026-11-15)

Added a Chromium browser regression case that starts a delayed Spot scan, switches to the USDⓈ-M scanner, and completes the newer USDⓈ-M scan before the older Spot response is released. The test asserts that the latest USDⓈ-M row remains visible, the superseded Spot response does not populate the Spot table, and the selected market/status remain consistent.

Test commit: `bd7ad870a62404b17eecb29da095a2efe5be1ef7` on `feat/institutional-dashboard-design`.

**Validation status:** committed; the new overlap/race test is not yet verified by a completed CI run or local Chromium execution. It must not be described as passed until an actual run is inspected. This is browser automation and does not replace physical-device or manual assistive-technology testing.

No dashboard application source, backend business logic, database, secrets, `main`, PR metadata, merge state, or deployment configuration was changed. No merge or deployment was performed.

The overlap test's empty-Spot assertion was tightened in follow-up commit `7d9a2b0a0fdb3915b34eeea363b78db53e457072`: it now checks the actual initial placeholder row text rather than assuming the table has zero rows. This is a test expectation correction, not an application change. The test remains pending CI execution.


## 64. Data-quality and research-readiness request-race regression coverage (2026-11-15)

Added two Chromium browser regression cases in `tests/test_dashboard_browser.cjs`:

- Data quality: starts a delayed BTCUSDT report, changes the selected symbol to ETHUSDT (which invalidates the active request), then confirms the newer ETHUSDT report remains displayed after the older response path settles.
- Research readiness: starts a delayed preflight request, starts the phase-readiness request, and confirms the newer readiness result and status are not overwritten by the late preflight response.

Test commit: `7f8dee0863eb7fe82059f2522a99c99fb3ac161d` on `feat/institutional-dashboard-design`.

**Validation status:** committed, but the two new browser cases have not yet been verified by a completed GitHub Actions run or local Chromium execution. They remain pending execution; prior green workflows do not validate these additions. The tests exercise mocked browser/API behavior and do not establish backend endpoint correctness.

Only the browser regression test file and this audit document were changed in this pass. No dashboard application source, backend business logic, database, migrations, secrets, `main`, PR metadata, merge state, or deployment configuration was changed. No merge or deployment was performed. Physical Android/iPhone testing and manual TalkBack/VoiceOver verification remain outstanding.


## 65. CI findings and browser-test synchronization corrections (2026-11-15)

The first CI execution of the Section 64 additions exposed two test-harness issues; it did not pass:

- Browser QA Run [43736841910](https://github.com/mamunfb/universal-binance-ai-backend/actions/runs/43736841910) completed with **17 passed, 2 failed**. The market-scan test asserted that a table row existed before the asynchronous newer scan had populated it. The readiness test attempted to click a control while its Overview page was hidden behind Settings.
- The failure log showed the two newly added cases themselves behaved as expected: the data-quality stale-response case passed; the readiness case timed out before it could start because the Overview page was not active.
- Full Backend and dashboard tests Run [43736853625](https://github.com/mamunfb/universal-binance-ai-backend/actions/runs/43736853625) completed successfully. This run validates the Python suite and JavaScript/document checks, not the browser suite.

Corrected the browser test synchronization in commit `bd327a74778fdf1d4ca9f573656e01f1ce9e8bd7`:
- Wait for the actual `CURRENTUSDT` content rather than the pre-existing empty-state table row.
- Navigate back to Overview before clicking the research-preflight control.

**Validation status:** these corrections are committed but have not yet been confirmed by a subsequent completed browser QA run. The next CI result is required before calling the browser suite green. No dashboard application source was changed.


## 66. Browser QA recovery and accumulated regression execution (2026-11-16)

The follow-up Chromium workflow completed successfully on feature-branch commit `b611c256f02181b9f96e55c7806f43f3bf91d498`:

- [Dashboard browser QA Run #43](https://github.com/mamunfb/universal-binance-ai-backend/actions/runs/43783483736): **success**. GitHub recorded successful setup, checkout, Node.js setup, pinned Playwright installation, Chromium/system dependency installation, and execution of the isolated browser test command.
- The browser test source at this commit contains **19 test cases**. The successful isolated browser-test step validates the current suite, including the previously pending API transport/cookie, mobile axe-core, health-request clearing, live-region semantics, overlapping scan, data-quality race, and research-readiness race coverage, as well as responsive layout, keyboard navigation and scanner pagination/search.
- [Backend and dashboard tests Run #1868](https://github.com/mamunfb/universal-binance-ai-backend/actions/runs/43783483742): **success**. The job completed its setup, dependency installation, document/script-reference validation, JavaScript syntax validation and feature-branch full Python/Chromium QA step. Its separate generic Python test step was skipped by workflow conditions; do not infer an additional pytest count from this run.

This closes the pending CI-execution status recorded in Section 65 for the corrected browser suite. The browser's backend responses are deterministic route mocks; no real Render backend or Cloudflare Pages cross-origin session was exercised. Physical Android/iOS testing, manual TalkBack/VoiceOver verification, live backend integration, Lighthouse/Core Web Vitals and production verification remain outstanding. No merge, deployment, backend/database change, secret change or `main` update was performed.


## 67. CI test-discovery correction and full-suite confirmation (2026-11-16)

The documentation-only commit that followed Section 66 exposed a Dashboard Frontend workflow failure: its `unittest discover -p "test_dashboard_*.py"` command also imported `tests/test_dashboard_browser.py`, which requires `pytest` and Playwright and is not a standard-library unittest module. The failure was a workflow test-selection/configuration issue, not a dashboard JavaScript runtime failure.

Corrected `.github/workflows/dashboard-frontend.yml` in commit `590fd526a9bef8e450a2c27d4083149827795dd7` by running `test_dashboard_contract.py` and `test_dashboard_accessibility.py` as separate unittest discovery targets. This keeps the Python standard-library contract checks isolated from the pytest/Playwright browser suite.

Validation on the corrected commit:
- [Dashboard frontend checks](https://github.com/mamunfb/universal-binance-ai-backend/actions/runs/43788713264): **success**; JavaScript syntax, chart fixtures and both dashboard unittest targets completed successfully.
- [Backend and dashboard tests](https://github.com/mamunfb/universal-binance-ai-backend/actions/runs/43788713276): **success**; feature-branch Playwright/Chromium installation, document/script-reference checks, JavaScript syntax and full pytest suite all completed successfully. Job log records **640 passed, 2 warnings**.

The generic Python suite step was skipped by workflow conditions on this feature-branch run; the full feature-branch pytest step is the executed suite represented by the 640-test result. Browser API responses remain deterministic mocks, not a live Render/Cloudflare cross-origin test. Physical Android/iOS, TalkBack/VoiceOver manual review, live backend integration and Lighthouse/Core Web Vitals remain separate verification tasks. No application source, backend business logic, database, secrets, `main`, PR metadata, merge state or deployment configuration was changed. No merge or deployment was performed.


## 68. Mobile Lighthouse, CPU-throttled interaction and heap profiling (2026-11-16)

Performance QA workflow [Run `43789369354`](https://github.com/mamunfb/universal-binance-ai-backend/actions/runs/43789369354) completed successfully on feature-branch commit `e250f30d6db67432e16774ba4fe2547f41539321`. Raw evidence artifact: [dashboard-performance-e250f30d6db67432e16774ba4fe2547f41539321](https://github.com/mamunfb/universal-binance-ai-backend/actions/runs/43789369354/artifacts/14191367649).

Three Lighthouse mobile cold-load samples against the local static QA server completed and each recorded a **Performance score of 1.00 (100/100)**. Across the three samples, First Contentful Paint was approximately 0.90 s; Largest Contentful Paint was 1.52–1.69 s (median approximately 1.65 s); Total Blocking Time was 0 ms; Cumulative Layout Shift was 0 or approximately 0.000024. These are Lighthouse simulated-mobile measurements of the local static page, not production/Cloudflare measurements. The workflow used the `perf` preset, so these runs do not provide Accessibility, Best Practices or SEO category scores.

The Playwright profile exercised a deterministic mocked 1,000-row Spot scanner fixture at 390×844 CSS px, with CPU throttle rates 1× and 4×:
- Both runs rendered the first 100-row page and filtered the fixture to one matching row; no page-level JavaScript errors were recorded.
- At 1×: initial navigation 29 ms, scanner render 67 ms, sort 36 ms, search 155 ms, pagination 70 ms; five repeated search/sort/page cycles took 2,343 ms.
- At 4×: initial navigation 49 ms, scanner render 91 ms, sort 79 ms, search 180 ms, pagination 109 ms; five repeated cycles took 2,925 ms.
- After explicit garbage collection and five repeated cycles, retained JS heap delta was 36,452 bytes at 1× and 64,796 bytes at 4×; DOM node delta was +5 in both runs. These single-run deltas are useful regression baselines, not proof that long-session memory leaks are absent.

The performance harness contained a duplicate `dom_nodes_before_cycles` object key. Removed the redundant duplicate in commit `e250f30d6db67432e16774ba4fe2547f41539321`; the value and measured behavior are unchanged.

Limits: browser API calls used deterministic route mocks; Lighthouse used the local static server and simulated mobile throttling. No live Render API, Cloudflare Pages origin, real network conditions, physical Android/iOS device, or manual TalkBack/VoiceOver session was tested. No production performance claim is made. No application behavior, backend business logic, database, secrets, `main`, PR metadata, merge state or deployment configuration was changed. No merge or deployment was performed.

## 69. GitHub-hosted live cross-origin browser integration harness (2026-11-16)

Added a feature-branch push workflow to bridge the gap between mocked browser tests and a live Cloudflare Pages Preview → Render backend session:

- `.github/workflows/dashboard-live-integration-qa.yml` reads the exact HTTPS dashboard URL and backend base URL from repository Actions variables `DASHBOARD_PREVIEW_URL` and `RENDER_BACKEND_URL`. If either is missing, the workflow reports that configuration is required and skips the browser job. Configure both under Settings → Secrets and variables → Actions → Variables; these are URL values, not credentials. It runs on GitHub-hosted Ubuntu 24.04, installs pinned Playwright 1.56.1 and Chromium, and launches a real headless Chromium browser.
- `tests/dashboard_live_integration.cjs` opens the provided dashboard origin at 390×844, enters the backend URL using the dashboard's own Settings UI, activates **Test Connection**, and asserts that the real health request succeeds, the health label reports `ok`/healthy, and the page emits no JavaScript exceptions.
- URL validation rejects non-HTTPS inputs, embedded credentials, query strings and fragments; the dashboard and backend must be different origins.
- The smoke test deliberately leaves the bearer token blank and exercises only the health endpoint. It does not establish that authenticated market-data routes work, that a CORS OPTIONS preflight succeeds, or that production performance is acceptable. Those require a separately authorized token/route test and confirmed CORS configuration.
- The workflow runs only on relevant pushes to `feat/institutional-dashboard-design`; it does not change deployment state, Render settings, secrets, CORS allowlists or production configuration. The exact Preview URL is not guessed and no wildcard origin is used.

Validation:
- Backend + Dashboard workflow [run 43790991040](https://github.com/mamunfb/universal-binance-ai-backend/actions/runs/43790991040) on feature-branch commit `abaef530a77be180e7e01bcaf0a6054d49fe7769`: **success**. The executed feature-branch pytest/Chromium step reports **640 passed, 2 warnings**; dashboard document/script references and JavaScript syntax checks also passed.
- The separate generic Python test step was skipped by workflow conditions. The run's executed full feature-branch pytest/browser step is the basis for the 640-test count.
- The live integration workflow has not yet completed a live run because the exact Cloudflare Pages Preview URL and repository Actions variables are not yet configured. Therefore no live Render/Cloudflare browser pass is claimed.

Outstanding: configure the exact Preview and Render URLs as repository Actions variables, then push a relevant feature-branch change to trigger the live workflow, test authenticated endpoints and preflight only after confirming safe CORS/API-key configuration, then perform physical Android/iOS and manual TalkBack/VoiceOver checks. No `main` update, PR creation/merge, deployment, Render setting change, CORS allowlist change, secret change, or backend/database logic change was performed.

## 32. Latest feature-branch CI and live-integration gate (2026-11-16)

Latest verified feature-branch head at this checkpoint: `78a277bcb0e1cd219f3b665ba806bb5e5986d82d`.

Backend + Dashboard workflow Run #43791191613 completed successfully on that exact commit:
- Job `133049802099` completed successfully on the GitHub-hosted Ubuntu runner.
- Dashboard HTML structure and both local script references were validated.
- `node --check dashboard/app.js` and `node --check dashboard/chart.js` passed.
- The full Python suite completed: **640 passed, 2 warnings** in 10.18 seconds.
- Warnings are deprecation warnings from Starlette/httpx TestClient usage and a FastAPI `example` parameter.
- The generic Python test step was skipped by its workflow condition; the full Python + Chromium feature-branch QA step ran and passed.

Run evidence: https://github.com/mamunfb/universal-binance-ai-backend/actions/runs/43791191613

The separate Dashboard Live Integration QA workflow Run #43791165393 completed its configuration-check job, but the actual cross-origin Chromium job was **skipped** because the repository Actions variables `DASHBOARD_PREVIEW_URL` and `RENDER_BACKEND_URL` were not configured. This is not a live Render/Cloudflare integration pass.

The live smoke test currently checks a 390x844 Chromium viewport, opens the supplied dashboard URL, configures the supplied backend origin without an API token, and verifies the public health endpoint's success state. It does not test authenticated endpoints or OPTIONS preflight. The exact Cloudflare Pages preview URL remains unverified.

Run evidence: https://github.com/mamunfb/universal-binance-ai-backend/actions/runs/43791165393

### Remaining live verification
1. Set exact HTTPS repository Actions variables `DASHBOARD_PREVIEW_URL` and `RENDER_BACKEND_URL` after confirming the real Pages preview URL.
2. Allow the feature-branch push workflow to run the live Chromium smoke test; inspect its job log, not only the overall run conclusion.
3. Separately verify authenticated API calls and CORS preflight with an approved test credential in GitHub Actions secrets; never put credentials in repository variables or logs.
4. Keep physical Android/TalkBack and iOS/VoiceOver checks marked pending until performed on real devices.

No production deployment, staging deployment, PR creation/merge, main-branch update, Render configuration change, or wildcard CORS allowance was performed.


## 33. Cross-origin and authenticated API source gate (2026-11-16)

A read-only source inspection was performed after Section 32 to determine whether the pending live cross-origin, authenticated API, and CORS preflight tests can safely run against the current feature-branch backend source.

Findings from `backend/app/main.py` on `feat/institutional-dashboard-design`:

- The FastAPI application is created without a visible `CORSMiddleware` registration or another CORS middleware registration in this entrypoint.
- The `request_tracking_middleware` applies its API-key handling to every request whose path starts with `/api/`.
- The middleware does not contain an `OPTIONS` preflight bypass before the API-key check. When a private key is configured, an unauthenticated browser preflight to an `/api/` path can therefore be rejected with HTTP 401 before the route is reached.
- The inspected `backend/app/config.py` does not declare a CORS allowed-origins setting.
- The existing live Chromium smoke test intentionally sends no Bearer token and tests only the health connection. It does not exercise a protected API route or an OPTIONS preflight.

**Conclusion:** the current source readback does not establish that the feature-branch backend is ready for cross-origin browser requests. The live smoke workflow must remain pending until an exact-origin CORS policy is implemented/configured in the backend deployment being tested, with preflight handled before API-key authentication. Do not use wildcard origins, do not bypass authentication for non-OPTIONS API requests, and do not put credentials in repository variables or logs.

**Execution blockers remain:**
1. The exact Cloudflare Pages Preview URL and repository Actions variables `DASHBOARD_PREVIEW_URL` and `RENDER_BACKEND_URL` are not configured/verified.
2. An approved, dedicated test Bearer credential is not yet available as a GitHub Actions secret for protected-route testing.
3. A strict CORS allowlist for the exact dashboard origin is not evidenced in the inspected feature-branch backend source or its settings model.
4. Physical Android/iOS testing and manual TalkBack/VoiceOver checks still require real devices and have not been performed.

**Next safe test sequence:** first verify/implement strict exact-origin CORS support in the backend branch intended for the live service; ensure OPTIONS preflight is answered without a Bearer token while protected GET requests still require a valid Bearer token; add regression tests for allowed origin, disallowed origin, requested Authorization header, unauthenticated preflight, missing/invalid token (401), and valid test token; then configure the exact Preview/backend URLs and a masked Actions secret and run the live Chromium workflow. Record actual response status and CORS headers from browser/network evidence. Do not change Render settings or deploy as part of this source-only checkpoint.

No source code, backend behavior, secrets, database, `main`, PR metadata, merge state, Render configuration, CORS deployment setting, or production deployment was changed during this inspection.


**Related existing implementation located:** a separate open Draft PR #30 branch, `fix/dashboard-cloudflare-pages-cors`, already contains a strict CORS implementation in `backend/app/config.py` and registers it after request-tracking middleware in `backend/app/main.py`. Its `tests/test_cors_configuration.py` covers exact HTTPS/local origins, wildcard/path/credential/insecure-origin rejection, allowed Authorization preflight, unlisted-origin rejection, and empty configuration. This implementation is not present in the current dashboard feature branch. It has not been merged; do not assume it is active in the live backend. Review its dependency/base-branch relationship before selectively porting or stacking it, and add explicit authenticated-route regression coverage before declaring the requested API checks complete.


## 34. Strict CORS implementation and authenticated-preflight regression tests (2026-11-16)

To remove the source-level preflight blocker identified in Section 33, strict CORS support and focused regression coverage were added to this feature branch only:

- `backend/app/config.py` adds the optional `CORS_ALLOWED_ORIGINS` setting and a parser that permits exact HTTPS origins (plus localhost HTTP for development), rejects wildcard/path/credential/query/fragment/invalid-port values, and normalizes hostname casing and default ports.
- The CORS middleware permits only GET/POST and Authorization/Content-Type headers, exposes X-Request-ID, disables cookie credentials, and uses a bounded preflight cache age. An empty allowlist grants no cross-origin access.
- `backend/app/main.py` registers CORS outside the request-tracking/API-key middleware so browser OPTIONS preflight is handled before Bearer authentication. Non-OPTIONS protected API requests remain subject to the existing API-key check.
- `tests/test_cors_configuration.py` adds coverage for safe parsing and normalization, unsafe-origin rejection, allowed and disallowed preflight, missing/invalid Bearer rejection, valid Bearer acceptance, and empty-allowlist behavior.

Implementation commits:
- `b50776cd02363db9c86aaeb8b2a6f19f888e8227` — strict exact-origin CORS configuration.
- `dd8beffaf336b4866e21d912800bbfa4aecb0191` — CORS middleware ordering before API authentication.
- `102197e507aca96e4fa68ae63971ad7af37310eb` — CORS and authenticated API regression tests.

**Validation status:** source files and commit diffs were read back from GitHub. At the time of this entry, no CI status/check record had yet been returned for the new test commit; therefore these tests are **pending execution**, not PASS. The live Cloudflare Pages → Render test is still blocked by the missing exact repository URL variables and dedicated masked test credential. No real Render response or browser preflight has yet been observed.

No wildcard CORS, production/main change, PR merge, Render setting change, secret change, database change, or deployment was performed.


## 35. Live browser test expanded to authenticated API and real preflight (2026-11-16)

Extended the live integration harness so a future configured run will test more than the public health endpoint:

- The live workflow now passes `DASHBOARD_QA_BEARER_TOKEN` from a GitHub Actions secret to the test process; the test validates that a sufficiently long token is present and never prints it.
- The Chromium test configures the dashboard with the QA token, verifies the public health endpoint, then calls the protected `GET /api/v1/research/phase-readiness` route from the dashboard origin.
- It asserts that the protected route returns **401 without a Bearer token** and **200 with the configured QA Bearer token**.
- It records the browser's actual OPTIONS response for that protected route and checks HTTP 200, the exact dashboard `Access-Control-Allow-Origin`, GET permission, Authorization-header permission, and absence of cookie-credential permission.
- The standard Backend + Dashboard workflow now runs `node --check tests/dashboard_live_integration.cjs` so the live harness receives a JavaScript syntax check even when live environment values are not configured.

Commits:
- `cbe69f3d54ae6bd09bf819d3432505e73a5cb38a` — pass the masked QA token to the live workflow.
- `6597729a7fdd0075db4466e69b2254ccf847f3b1` — add authenticated API and preflight assertions.
- `9e10e55cd41bf541287032a8c5bb6e8bbabfc1ca` — scope preflight evidence to the protected route.
- `ebbf1e8a75fc1c181930268f9a78a35b51a9094e` — syntax-check the live test in standard CI.

**Validation status:** these changes have been read back from the feature branch, but no post-change CI result or live browser run is yet confirmed. The live run requires all three owner-provided inputs: exact HTTPS `DASHBOARD_PREVIEW_URL` and `RENDER_BACKEND_URL` repository variables, plus `DASHBOARD_QA_BEARER_TOKEN` as a masked Actions secret. The backend deployment must already have the exact dashboard origin in its strict `CORS_ALLOWED_ORIGINS` allowlist and the token must be valid there. This audit did not change Render settings or secrets.

No production deployment, staging deployment, `main` update, PR merge, wildcard CORS, Render configuration change, or credential disclosure was performed.


## 36. Post-CORS feature-branch CI verification (2026-11-16)

The latest feature-branch CI run for commit `496d48178d2d20617ed948489c1eb266fa549109` has completed successfully:

- Workflow: Backend and dashboard tests, Run #1901
- Run ID: `43793379013`
- Overall conclusion: **success**
- Toolchain setup: success
- Python test dependency installation: success
- Playwright + Chromium installation: success
- Dashboard HTML/script-reference validation: success
- Dashboard JavaScript and live integration harness syntax checks: success
- Full Python + Chromium browser QA step: success

The workflow intentionally skips the separate Python-only test step for this feature branch because the full feature-branch step runs `python -m pytest -q`; that full-suite step completed successfully. The GitHub job summary exposed no exact test count in the retrieved run metadata, so no test count is asserted here.

**Important distinction:** the successful local-browser/fixture-backed Chromium suite is not the live Cloudflare Pages → Render integration test. The live workflow Run #6 completed its URL-configuration explanation job successfully, while the actual live cross-origin Chromium job was **skipped** because the required repository variables were not available. Therefore no live Render CORS response, authenticated request, or real preflight has yet been verified.

**Next gates:**
1. Supply exact HTTPS `DASHBOARD_PREVIEW_URL` and `RENDER_BACKEND_URL` repository Actions variables.
2. Supply `DASHBOARD_QA_BEARER_TOKEN` as a masked Actions secret; never put it in a variable, commit, issue, or log.
3. Ensure the backend instance being tested has the exact dashboard origin in `CORS_ALLOWED_ORIGINS` and the QA token is valid for that instance.
4. Re-run the live workflow and retain actual browser response/header evidence for health, unauthenticated 401, authenticated 200, and OPTIONS preflight.
5. Continue physical-device keyboard/viewport testing and real Android TalkBack/iOS VoiceOver checks.

No main-branch change, PR merge, Render setting change, secret change, wildcard CORS, or deployment was performed for this verification.


## 37. Keyboard focus regression and CI #1903 verification (2026-11-16)

Added a focused Playwright regression test in `tests/test_dashboard_browser.cjs`:
- Starts keyboard navigation with Tab at a 390 × 844 viewport.
- Verifies the first focus stop at the 390 px mobile viewport is the mobile navigation button (the sidebar brand link is inert while the mobile sidebar is closed).
- Checks computed focus styling is a solid, non-transparent 2 CSS-pixel outline.
- Confirms no browser page errors are raised during the check.

Commit: `b5855b3cf5df2eb0d646302e87ff8f0802b22a91`.

Backend + Dashboard workflow Run #1903 (`43793582340`) completed with **success** on that commit. The job completed the full feature-branch `python -m pytest -q` step successfully, along with runner setup, dependency installation, Playwright/Chromium installation, dashboard HTML/script-reference validation, and JavaScript syntax checks. The separate Python-only step is intentionally skipped on the feature branch because the full feature-branch test command includes Python and Chromium tests.

Dedicated Chromium QA Run #44 (`43793582323`) completed with 19 of 20 tests passing. The new focus test initially failed because it incorrectly expected the sidebar brand link to be the first Tab stop, while the closed mobile sidebar is inert and the mobile menu button is the correct first stop. This was a test expectation error, not evidence of a missing focus outline. The assertion has been corrected to target `#mobile-menu` and verify its visible 2 px focus outline. The corrected test is queued in Run #45 (`43793740587`) and the full suite in Run #1905 (`43793740723`); their results remain pending.

**Still not verified:** the live Cloudflare Pages → Render cross-origin test remains blocked by missing exact HTTPS repository variables and the masked QA Bearer secret. Real Android TalkBack and iOS VoiceOver checks remain unperformed and require physical devices.

No `main` change, PR merge, Render configuration/secret change, wildcard CORS, or deployment was performed.


## 38. Corrected mobile keyboard-focus test and CI verification (2026-11-16)

The corrected mobile keyboard-focus test has now passed in the dedicated Chromium workflow:
- Dashboard Browser QA Run #45, run ID `43793740587`, commit `1816a4ac7ec4a859e44a21c0413618eb335cb157`.
- Result: **20 passed, 0 failed, 0 skipped**.
- The test confirms that at a 390 × 844 mobile viewport the first Tab stop is `#mobile-menu`, and its computed focus outline is solid, 2 px wide, and non-transparent.
- The test title was clarified to identify the mobile menu button rather than incorrectly describing it as the first dashboard link.

Backend + Dashboard Run #1906, run ID `43793771904`, completed successfully on commit `8a6a5c7f52a9728f24de125c530a92e1207f5dce`:
- Full feature-branch `python -m pytest -q`: **661 passed** in 11.17 seconds.
- Dashboard HTML/script-reference validation and JavaScript syntax checks: success.
- The full Python + Chromium QA step: success.
- Two deprecation warnings were emitted by installed Starlette/FastAPI dependencies; they did not fail the test run.
- The separate Python-only workflow step is skipped by design on this feature branch because the full-suite step is used instead.

The two successful runs above cover adjacent commits: Browser QA #45 tested the code commit `1816a4a...`; Backend + Dashboard #1906 tested documentation commit `8a6a5c7...`. A title-only test clarification is being committed now and will trigger fresh workflows.

Live Cloudflare Pages → Render integration is still not verified: exact HTTPS Actions variables and the masked QA Bearer secret are not configured/available to the workflow. Physical-device TalkBack and VoiceOver testing also remains outstanding.

No `main` change, PR merge, Render configuration/secret change, wildcard CORS, or deployment was performed.


## 39. Latest CI verification and strict origin syntax edge cases (2026-11-16)

The latest complete QA runs have been inspected from their job logs:

- Dedicated Dashboard Browser QA Run #46 (`43793995990`), commit `707b110616a4f51a0bc6f8e140bf200137e43e3e`: **20 passed, 0 failed, 0 skipped**.
- Backend + Dashboard Run #1908 (`43794000609`), commit `cef2648b1669e6b6d6b18bab22ea6e8d25a6bc2b`: full Python suite **661 passed**, 2 dependency deprecation warnings, in 11.17 seconds. Dashboard HTML/script references, JavaScript syntax and full Python + Chromium feature-branch QA also succeeded.

A small strictness gap was then identified in CORS origin parsing: `urlsplit` returns empty query/fragment values for syntactically present empty delimiters (`?` and `#`). Since a CORS allowlist entry must be an origin, not a URL with query/fragment delimiters, the parser now explicitly rejects those characters and regression cases cover both empty forms.

These parser and test changes are being validated by new CI runs. They are not yet counted as passed until those runs complete.

Live Cloudflare Pages → Render integration remains unverified because the exact HTTPS Actions variables and masked QA Bearer secret are not configured/available to the workflow. No production, Render, main-branch, PR merge, or deployment change was made.

## 40. CORS method and request-header allowlist regression coverage (2026-11-16)

Added negative preflight tests to ensure the browser CORS policy remains narrow:
- `PUT`, `PATCH`, and `DELETE` preflights return HTTP 400 because the configured allowlist permits only `GET` and `POST`.
- A preflight requesting the unlisted `X-Admin-Override` header returns HTTP 400, even when `Authorization` is also requested.

The first test revision made an incorrect assertion that Starlette's CORS middleware must omit `Access-Control-Allow-Origin` for an allowed origin when the requested method/header is rejected. Run #1913 exposed this test-expectation error: the middleware correctly returned HTTP 400 while retaining the exact allowed origin header. The tests were corrected to assert HTTP 400 and verify the requested method/header is absent from the corresponding allowlist response headers.

Commits:
- `8ab360bfb0d678df03d28ad9b33086a127ad2806` — initial negative preflight cases.
- `80f3da039feee4f7b4e32d6820b0d60c804ab23c` — correct assertions against the middleware's actual rejection behavior.

Run #1913 (`43794399063`) on the initial revision failed: **663 passed, 4 failed, 2 warnings**. All four failures were in the new assertions described above; dashboard HTML/script-reference validation and JavaScript syntax checks succeeded. The corrected tests are awaiting a fresh CI run and are not yet counted as passing.

The dedicated browser QA previously passed 20/20 on commit `707b110616a4f51a0bc6f8e140bf200137e43e3e`; this does not constitute physical Android/iOS or assistive-technology verification. Live Cloudflare Pages → Render authenticated CORS integration remains unverified because the exact HTTPS Actions URL variables and masked QA token are not configured for the workflow.

No `main` update, PR merge, Render configuration change, secret change, wildcard CORS, or production/staging deployment was performed.

## 70. Corrected CORS preflight regression tests — CI verified (2026-11-16)

The corrected negative-preflight assertions passed in Backend and Dashboard CI Run #1915:
- Run ID: `43794577028`
- Commit: `101b66f401737b676aafaf4ba5c2a265b005fe59`
- Overall conclusion: `success`
- Full feature-branch pytest suite: **667 passed, 2 warnings in 11.54s**
- Dashboard HTML structure and both local script references validated.
- `node --check` passed for `dashboard/app.js`, `dashboard/chart.js`, and `tests/dashboard_live_integration.cjs`.
- The feature-branch pytest command includes `tests/test_dashboard_browser.py` and ran under the Playwright Chromium installation step.

The two warnings are dependency deprecations: Starlette TestClient/httpx integration and FastAPI's deprecated `example` parameter. They did not fail the suite.

The separate live integration workflow Run #10 (`43794555831`) completed its configuration-check job but **skipped** the live cross-origin Chromium job because the required exact HTTPS repository variables are not configured. Therefore this CI result does not prove a real Cloudflare Pages → Render connection or production CORS behavior.

The preceding Run #1913 remains recorded as an initial failed test revision (663 passed, 4 failed); Run #1915 is the corrected, passing revision. No production deployment, Render change, secret change, PR merge, or `main` update occurred.

## 71. QA audit documentation commit verification (2026-11-16)

The audit update from Section 41 was itself checked by Backend and Dashboard CI Run #1916:
- Run ID: `43794784200`
- Commit: `4bdc0d961ee64432f3f9b4d334d489fc00030ce2`
- Conclusion: `success`
- Full feature-branch test suite: **667 passed, 2 warnings in 10.08s**
- Dashboard HTML/script-reference validation passed (2 local scripts).
- JavaScript syntax checks passed for dashboard app, chart, and live integration test scripts.
- The feature-branch workflow ran the full pytest command with Playwright Chromium installed; the standalone Python-only step is intentionally skipped on this branch to avoid running the suite twice.

Browser regression coverage currently includes responsive viewport overflow, mobile keyboard focus and navigation focus trapping/restoration, axe-core WCAG 2.1 A/AA scans on desktop and mobile navigation states, reduced-motion preference, API success/error/timeout/malformed response handling, text-only rendering of backend errors, cookie exclusion and no-store requests, cancellation and stale-response ordering, live-region semantics, and a 1,000-row scanner pagination/search/sort scenario. These are automated Chromium tests with local static serving and mocked backend responses; they are not physical-device tests or a live production integration.

The two dependency deprecation warnings remain: Starlette TestClient/httpx integration and FastAPI's deprecated `example` parameter. No production deployment, Render configuration change, secret change, PR merge, or `main` update occurred.

## 72. Latest audit-head CI confirmation and audit numbering reconciliation (2026-11-16)

Backend and Dashboard CI Run #1917 verified the preceding audit-head commit:
- Run ID: `43794995094`
- Commit: `2f6bc9cdc4a66b12253b56ebc179bbff6ede5b32`
- Conclusion: `success`
- Full feature-branch pytest suite: **667 passed, 2 warnings in 10.50s**
- Dashboard HTML and two local script references validated.
- JavaScript syntax checks passed for `dashboard/app.js`, `dashboard/chart.js`, and `tests/dashboard_live_integration.cjs`.
- Playwright Chromium setup completed and the full feature-branch pytest command passed.

The two warnings remain dependency deprecations (Starlette TestClient/httpx integration and FastAPI's deprecated `example` parameter). The full feature-branch pytest suite includes the Playwright browser tests; the separate Python-only step is intentionally skipped to avoid duplicate execution.

Audit heading reconciliation: the earlier two additions had been appended after historical Section 69 but mistakenly reused the labels 41 and 42. Their headings are now corrected to Sections 70 and 71, preserving the existing historical sections and restoring a continuous sequence.

No production deployment, Render configuration change, secret change, PR merge, or `main` update occurred.


## 73. Latest audit-head CI verification (2026-11-16)

Backend and Dashboard workflow Run #1919 verified the current feature-branch head:
- Run ID: `43795187369`
- Commit: `1938a82d15d4edb7ae12e54577eda269b811aa97`
- Conclusion: **success**; job `133062330797` completed successfully.
- Full feature-branch pytest suite: **667 passed, 2 warnings in 11.01s**.
- Dashboard HTML validation confirmed both local script references.
- JavaScript syntax checks passed for `dashboard/app.js`, `dashboard/chart.js`, and `tests/dashboard_live_integration.cjs`.
- Playwright Chromium setup and the full feature-branch Python + browser QA step completed successfully. The separate Python-only step is intentionally skipped to avoid duplicate suite execution.

The two warnings remain dependency deprecations (Starlette TestClient/httpx integration and FastAPI's deprecated `example` parameter). They did not fail the suite.

The adjacent Run #1918 (`43795178051`, preceding commit `2c603f4...`) was cancelled when the newer head run superseded it; it is not the final-head validation. The final-head Run #1919 is successful.

The live Cloudflare Pages → Render workflow Run #10 (`43794555831`) had a successful configuration-check job, but its live cross-origin Chromium job was **skipped** because the required exact HTTPS repository variables were unavailable. The live authenticated health/API/preflight integration is therefore still unverified. The required owner-managed inputs remain `DASHBOARD_PREVIEW_URL`, `RENDER_BACKEND_URL`, and masked secret `DASHBOARD_QA_BEARER_TOKEN`; do not put the token in a repository variable, source file, or chat.

Current branch-head verification: `feat/institutional-dashboard-design` points to `1938a82d15d4edb7ae12e54577eda269b811aa97`. The `main` ref remains `0e3b921ab83e18d4999c1eac87f45285a0f27b26`. No PR merge, Render configuration/secret change, wildcard CORS, or production/staging deployment was performed.


## 74. Retrieved mobile Lighthouse and CPU/heap benchmark evidence (2026-11-16)

The raw performance artifact from Dashboard performance QA Run #25 was downloaded and inspected, rather than relying only on the workflow's green conclusion:
- Run ID: `43789369354`; job ID: `133044073143`.
- Benchmark source commit: `e250f30d6db67432e16774ba4fe2547f41539321` (this is an earlier feature-branch commit, not the current audit head).
- Artifact ID: `14191367649`; four files: three raw mobile Lighthouse JSON reports and `browser-profile.json`.
- The job completed successfully; all three Lighthouse runs, CPU/heap browser profiling, and raw artifact upload succeeded.

**Three simulated mobile Lighthouse cold-load samples** (390 × 844, Lighthouse mobile preset, simulated throttling):
- Performance category score: **1.00 in all three samples**.
- First Contentful Paint: **0.903–0.905 s**.
- Largest Contentful Paint: **1.524–1.694 s** (median approximately **1.655 s**).
- Total Blocking Time: **0 ms** in all three samples.
- Cumulative Layout Shift: **0 to 0.000024**.
- Main-thread work: approximately **164–263 ms**.

**CPU-throttled 1,000-row scanner fixture** (deterministic mocked API data, 100 visible rows/page):
- At 1× CPU: scan render **67 ms**, sort **36 ms**, search **155 ms**, pagination **70 ms**.
- At 4× CPU throttling: scan render **91 ms**, sort **79 ms**, search **180 ms**, pagination **109 ms**.
- Five repeated search/sort/pagination cycles took **2.343 s** at 1× and **2.925 s** at 4×.
- After explicit garbage collection, JS heap delta was **36,452 bytes** at 1× and **64,796 bytes** at 4×; DOM node delta was **+5** in each run. These two post-cycle samples do **not** prove absence of a long-term memory leak or establish a stable memory-growth trend.
- No browser page errors were recorded in either CPU profile sample.

**Optimization evidence / limitations:** Lighthouse consistently identified approximately **59 KiB** of estimated unused JavaScript on the initial page (app.js and chart.js), and render-blocking CSS with an estimated **110–152 ms** opportunity. It also reported missing text compression in the local static QA server. These are follow-up optimization candidates, not measured production savings. The local QA server does not emulate Cloudflare compression/cache behavior, and these measurements do not represent a real phone, production network, or live backend. Lighthouse emitted non-fatal Lantern messages that the all-frames FCP/LCP computations are not implemented; the standard FCP/LCP metrics above were still present in the reports.

**Freshness gate:** this artifact is from commit `e250f30...`, while the current branch head at this audit update is later. Do not present these measurements as a fresh benchmark of the latest source until the performance workflow is run against the latest dashboard commit. No production performance claim is made.

No Render setting, secret, deployment, `main`, or PR merge was changed.


## 75. Latest feature-branch CI verification (2026-11-16)

Backend and Dashboard workflow Run #1921 verified the audit-head commit:
- Run ID: `43795597840`
- Commit: `efbce60b13e026f18db70b7899aec665b0d7d854`
- Job ID: `133063572030`
- Job conclusion: **success**.
- Full Python suite: **667 passed, 2 warnings in 11.41s**.
- Dashboard HTML validation confirmed the document shell and both local script references.
- JavaScript syntax checks passed for `dashboard/app.js`, `dashboard/chart.js`, and `tests/dashboard_live_integration.cjs`.
- Playwright Chromium installation completed and the combined feature-branch Python + browser QA step passed. The separate Python-only workflow step was skipped intentionally because the combined step runs the full suite once.

The two warnings remain dependency deprecations: Starlette TestClient/httpx integration and FastAPI's deprecated `example` parameter. They did not fail the test suite.

The performance workflow already includes `workflow_dispatch` and dashboard-source path filters. This provides a manual GitHub Actions rerun path; no workflow change was needed. A fresh performance benchmark has not yet been run against this audit-head commit, so Section 74's older benchmark must not be represented as current-head evidence.

The current feature-branch commit is the SHA listed above. The previously verified `main` SHA remains `0e3b921ab83e18d4999c1eac87f45285a0f27b26`; no change to `main` was requested or made. No PR merge, Render configuration/secret change, wildcard CORS, or production/staging deployment was performed.


## 76. Fresh performance QA and enforced interaction invariants (2026-11-16)

The Dashboard performance QA workflow ran against the then-current source commit:
- Workflow Run #1923; run ID: `43796077835`.
- Source commit: `7f1fd784431cc20948e11992ad877a93fa360c41`.
- Job ID: `133065073990`; conclusion: **success**.
- Raw artifact ID: `14194192989`; artifact name: `dashboard-performance-7f1fd784431cc20948e11992ad877a93fa360c41`.
- Artifact SHA-256: `3ba55ce18b95420dfdbd5a65686f291466cfe84081f0c76dd642dd8476af5cdb`.
- The artifact contains three raw mobile Lighthouse JSON reports and `browser-profile.json`; these were downloaded and inspected.

**Lighthouse samples (390 × 844, simulated mobile throttling, local static QA server):**
- Performance scores: **0.91, 1.00, 1.00**.
- First Contentful Paint: **0.902–0.904 s**.
- Largest Contentful Paint: **1.653–2.037 s**.
- Total Blocking Time: **0 ms, 367 ms, 0 ms**.
- Cumulative Layout Shift: **0 to approximately 0.000024**.
- One sample had a measurable TBT outlier (367 ms) and lower score (0.91); do not hide this sample or describe all three runs as identical. The two other samples had 0 ms TBT and score 1.00.
- All three reports estimated approximately 59 KiB unused JavaScript and 75 KiB potential text-compression savings. The latter is measured against the local static QA server and is not evidence that the production Cloudflare edge lacks compression.
- Lighthouse emitted non-fatal Lantern messages that all-frames FCP/LCP computations are not implemented; standard page FCP/LCP values were present.

**CPU-throttled 1,000-row mocked scanner fixture:**
- At 1× CPU: initial navigation 61 ms; scanner render 67 ms; sort 38 ms; search 163 ms; pagination 107 ms; five repeated cycles 2,485 ms; post-GC heap delta +77,024 bytes; DOM delta +5.
- At 4× CPU: initial navigation 65 ms; scanner render 134 ms; sort 96 ms; search 201 ms; pagination 131 ms; five repeated cycles 3,477 ms; post-GC heap delta +68,184 bytes; DOM delta +2.
- Both profiles rendered 100 visible rows from the 1,000-row fixture, returned one row for the unique-symbol search, and recorded no browser page errors.
- All 12 sampled in-app navigation actions closed the sidebar as expected in each CPU profile.
- These short, deterministic mock-data runs do not prove production performance, physical-device behavior, or absence of a long-term memory leak.

The benchmark harness now fails on browser page errors, mock API request failures/non-200 responses, a sidebar left open after navigation, or unexpected scanner visible/search row counts. These assertions were added in commit `7f1fd784...` and the successful performance run confirms they executed without triggering. The backend/dashboard CI for the same commit also succeeded: Run #1923 ID `43796077857`, with **667 passed, 2 warnings in 12.95s**, dashboard HTML/script validation, JavaScript syntax checks, and full Chromium browser QA.

The two Python warnings remain the known Starlette TestClient/httpx and FastAPI deprecated `example` warnings. No production deployment, staging deployment, Render configuration or secret change, wildcard CORS, PR merge, or `main` update occurred.


## 77. Latest dashboard/backend CI confirmation (2026-11-16)

Backend and Dashboard workflow Run #1924 verified the current audit-head commit:
- Run ID: `43796389980`.
- Commit: `9980aa20a971e804ef1d971f3a95006056a13375`.
- Job ID: `133066057865`; conclusion: **success**.
- Full feature-branch pytest suite: **667 passed, 2 warnings in 12.22s**.
- Dashboard HTML validation confirmed the app shell and both local script references (`chart.js` and `app.js`).
- JavaScript syntax checks passed for `dashboard/app.js`, `dashboard/chart.js`, and `tests/dashboard_live_integration.cjs`.
- The combined Python + Chromium browser QA step passed. The standalone Python-only step was skipped by design to avoid running the same suite twice.

The two warnings remain dependency deprecations: Starlette TestClient/httpx integration and FastAPI's deprecated `example` parameter. They did not fail the suite.

The performance workflow Run #26 remains the latest raw performance evidence described in Section 76. Its source commit is `7f1fd784...`, earlier than this audit-head commit; therefore its Lighthouse and CPU/heap numbers are not claimed as measurements of this exact commit. A separate physical-device test and live Cloudflare Pages → Render integration are still not established by this run.

No `main` update, PR merge, Render configuration/secret change, wildcard CORS, or production/staging deployment was performed.



## 78. Current-head script transfer timing and fresh performance QA (2026-11-16)

Dashboard Performance QA Run #27 and Backend + Dashboard CI Run #1926 both verified source commit `c9d9c83cdca019e3ac299d9ca043379008a4fc6b` on `feat/institutional-dashboard-design`.

**Workflow verification:**
- Performance Run #27: run ID `43796849174`; job ID `133067493717`; conclusion: **success**.
- Backend + Dashboard CI Run #1926: run ID `43796849084`; job ID `133067493504`; conclusion: **success**.
- CI log: **667 passed, 2 warnings in 11.69s**. Dashboard HTML validation confirmed both local script references; JavaScript syntax checks passed for `dashboard/app.js`, `dashboard/chart.js`, and `tests/dashboard_live_integration.cjs`; the combined Python + Chromium browser QA step passed. The separate Python-only step was skipped by design to avoid duplicate suite execution.
- The two warnings remain dependency deprecations: Starlette TestClient/httpx integration and FastAPI's deprecated `example` parameter.
- Performance run completed all three mobile Lighthouse report generations, CPU-throttled browser/heap profiling, and artifact upload.
- Raw artifact: ID `14194707645`; name `dashboard-performance-c9d9c83cdca019e3ac299d9ca043379008a4fc6b`; SHA-256 `cff2b1ed42226a36325236967009f503d3acd5bc96843ddb940953f01df783f6`; four files uploaded (three Lighthouse JSON reports and `browser-profile.json`).

**New script resource-timing evidence** (390 × 844 local static QA browser; no compression configured by this local server):
- At 1× CPU, `app.js`: 45,711 encoded/decoded body bytes, 46,011 transfer bytes, 8.4 ms resource duration; `chart.js`: 23,658 encoded/decoded body bytes, 23,958 transfer bytes, 8.4 ms duration.
- At 4× CPU, `app.js`: 45,711 encoded/decoded body bytes, 46,011 transfer bytes, 10.6 ms duration; `chart.js`: 23,658 encoded/decoded body bytes, 23,958 transfer bytes, 9.2 ms duration.
- Both scripts were present with non-zero decoded bodies; the harness now records and validates this rather than silently omitting missing resources.

**CPU-throttled 1,000-row mocked scanner fixture:**
- At 1× CPU: initial navigation 29 ms; scan render 67 ms; sort 39 ms; search 171 ms; pagination 72 ms; five repeated cycles 2,452 ms; post-GC heap delta +67,004 bytes; DOM delta +5.
- At 4× CPU: initial navigation 56 ms; scan render 99 ms; sort 78 ms; search 182 ms; pagination 134 ms; five repeated cycles 3,295 ms; post-GC heap delta +63,232 bytes; DOM delta +2.
- Both profiles rendered 100 visible rows from the 1,000-row fixture, unique search returned one row, all 12 sampled navigation actions left the sidebar closed, and no browser page errors were recorded.
- These deterministic, short mock runs do not establish production performance, real-device behavior, or absence of a long-term memory leak. The resource transfer sizes are local uncompressed measurements and must not be interpreted as production Cloudflare transfer sizes.

The performance harness enhancement was committed in `c9d9c83...` and is test-only; no dashboard runtime code was changed in this commit. The three Lighthouse JSON reports were downloaded from the artifact and inspected directly (390 × 844, Lighthouse mobile preset with simulated throttling, local static QA server):
- Performance category scores: **0.96, 1.00, 1.00**.
- First Contentful Paint: **902.9–906.8 ms**.
- Largest Contentful Paint: **1,502.9–1,763.8 ms**.
- Total Blocking Time: **0 ms, 210.6 ms, 0 ms**; the first sample has a measurable blocking-time outlier and must not be hidden.
- Cumulative Layout Shift: approximately **0.0000238** in all three samples.
- Estimated unused JavaScript opportunity: **60,333 bytes**; estimated text-compression savings: **76,974 bytes**. These are Lighthouse estimates against the local QA server, not confirmed production savings or evidence about Cloudflare edge compression.
- Lighthouse emitted non-fatal all-frames FCP/LCP computation warnings; standard page FCP/LCP metrics were present in the reports.

No `main` update, PR merge, Render configuration or secret change, wildcard CORS, or production/staging deployment occurred.



## 79. Latest 3-hour chart regression, browser QA and performance evidence (2026-11-16)

The current feature branch head is `5f3ac728f9b2976a623f6e6ba2faba7a9c84db22` (`Test 3-hour chart request and aggregation`).

**Current-head CI:**
- Dashboard frontend checks Run ID `43811201799`, commit `5f3ac728...`: **success**. JavaScript syntax, dashboard chart fixtures and Python dashboard contract tests all passed.
- Backend and dashboard tests Run ID `43811201698`, commit `5f3ac728...`: **success**. Full pytest suite: **686 passed, 2 warnings in 13.81s**. The separate Python-only step was skipped because the combined feature-branch Python + Chromium QA step ran successfully.
- Dashboard browser QA Run ID `43811198114`, commit `008bfe9e...`: **success**. The retained job log reports **20 tests passed, 0 failed, 0 skipped**. Coverage includes supported responsive widths without horizontal overflow; visible keyboard focus; mobile sidebar focus trap, Escape and focus restoration; API 503, malformed JSON, network failure and timeout handling; 1,000-row scanner pagination/search/keyboard sorting; automated WCAG 2.1 A/AA checks; and asynchronous stale-response ordering.
- Dashboard performance QA Run ID `43811198133`, commit `008bfe9e...`: **success**. Lighthouse, CPU-throttled browser/heap profiling and raw artifact upload all completed. Raw artifact ID `14200666615`, SHA-256 `86168ee831156acb452a777164dd4a0008b283215e90843058431361b9aa277e`; downloaded and inspected in this audit.
- The browser and performance runs were triggered for `008bfe9e...`, the chart-loader code fix. The later regression-test commit `5f3ac728...` has current-head frontend and backend/dashboard CI success, but the browser/performance workflows have not yet been re-run on that exact commit. Keep that commit distinction explicit.

**Performance artifact measurements** (390 × 844 Chromium, local static QA server, Lighthouse mobile preset/simulated throttling):
- Lighthouse Performance scores: **0.96, 1.00, 1.00**.
- First Contentful Paint: **902.7–906.3 ms**.
- Largest Contentful Paint: **1,652.8–1,805.3 ms**.
- Total Blocking Time: **0 ms, 0 ms, 209 ms**.
- Cumulative Layout Shift: **0 to approximately 0.0000238**.
- The first sample's 209 ms TBT and 0.96 score are retained as a real sample, not averaged away.
- On the 1,000-row mocked scanner fixture, 100 rows were visible on the first page and the unique-symbol search returned one row. At 1× CPU: render 67 ms, sort 38 ms, search 156 ms, pagination 68 ms. At 4× CPU: render 102 ms, sort 96 ms, search 188 ms, pagination 137 ms.
- Five repeated scanner interaction cycles: 2,401 ms at 1× and 3,311 ms at 4×. Post-GC heap deltas were +31,264 bytes and +70,360 bytes respectively; DOM deltas were +5 and +2. These short samples do not establish absence of a long-term memory leak.
- No browser page errors were recorded in either CPU profile.
- Local uncompressed resource timing: app.js 46,829 body bytes and chart.js 23,663 body bytes in both profiles. This is local QA-server transfer evidence, not production Cloudflare transfer size or compression evidence.
- Lighthouse estimates of unused JavaScript/compression opportunities are local diagnostic candidates only; no production savings are claimed.

**Live integration gate:** Live integration workflow Run ID `43811198164` completed its configuration-check job successfully, but the actual `Live cross-origin Chromium smoke test` job was **skipped**. The workflow explicitly requires Actions repository variables `DASHBOARD_PREVIEW_URL` and `RENDER_BACKEND_URL`; its live test also optionally reads `DASHBOARD_QA_BEARER_TOKEN`. No values were created or changed. Therefore Cloudflare Pages → Render live connectivity remains unverified.

**3h regression:** The loader now admits the custom `3h` timeframe, requests hourly candles, and aggregates only complete UTC-aligned three-hour buckets. The regression test was added in commit `5f3ac728...`; its chart fixture passed in the current-head frontend workflow. Existing indicator rendering was not intentionally removed or altered by this targeted fix.

**Change control:** No `main` update, PR merge, production or staging deployment, Render configuration/secret change, or CORS relaxation was performed. The branch head remains `5f3ac728...`.



## 80. Audit-documentation commit CI confirmation (2026-11-16)

The audit documentation update itself is now the feature-branch head:
- Commit: `5b950388c92e2e8187b53d8ac2530d0d80626569` (`docs: record latest dashboard QA evidence`).
- Backend and dashboard workflow Run ID: `43811642197`.
- Job ID: `133114392409`; job conclusion: **success**.
- Full Python suite: **686 passed, 2 warnings in 10.85s**.
- Dashboard HTML/script-reference validation and JavaScript syntax validation: **success**.
- Combined feature-branch Python + Chromium browser QA step: **success**.
- The separate Python-only step was skipped by design because the combined step runs the suite once.

The exact current head `5b950388...` changes only `docs/DASHBOARD_QA_AUDIT.md`; dashboard source and browser/performance harness files are unchanged from `5f3ac728...`. Therefore the source behavior covered by the current-head CI remains the same as the prior chart-loader and regression-test commits.

The standalone 20-test Chromium browser workflow and Lighthouse/performance workflow have not been re-run on `5b950388...`. Their latest detailed evidence remains tied to `008bfe9e...`, as stated in Section 79. Both workflow YAML files expose `workflow_dispatch`, but the connected GitHub action interface available in this session does not expose a workflow-dispatch operation. No fake dispatch, source-only trigger commit, or deployment workaround was used.

No `main` update, PR merge, production/staging deployment, Render setting/secret change, or CORS relaxation was performed.


## 81. Current feature-branch head CI verification (2026-11-16)

The feature branch head `fd351936777884b8c73aaf6c33fae8dd839ab2aa` (`docs: confirm audit commit CI evidence`) was verified by Backend and dashboard tests Run #1951:
- Run ID: `43811810701`; job ID: `133114909136`; job conclusion: **success**.
- Dashboard HTML validation confirmed the document doctype, app shell, both `chart.js` and `app.js` references, and that local referenced scripts exist.
- JavaScript syntax validation passed for `dashboard/app.js`, `dashboard/chart.js`, and `tests/dashboard_live_integration.cjs`.
- Full pytest suite: **686 passed, 2 warnings in 10.80s**.
- The feature-branch pytest invocation includes `tests/test_dashboard_browser.py`, which launches Chromium through Playwright. The browser test module includes dashboard runtime-error checks, responsive viewport checks at 360/390/768/1280px, and mobile navigation Escape/focus restoration checks. This is distinct from the standalone Node-based 20-test browser workflow cited in Section 79.
- The two warnings are dependency deprecations: Starlette TestClient/httpx integration and FastAPI's deprecated `example` parameter. They did not fail the run.

**Evidence boundaries and remaining gates:**
- This run was triggered by a documentation-only commit. It verifies the current source tree through the general Python/pytest + JavaScript validation workflow; it does not refresh the standalone browser QA or Lighthouse/performance artifacts.
- The standalone browser and performance workflow evidence remains tied to earlier dashboard source commits, as described in Section 79. The current workflow YAML exposes manual dispatch, but no dispatch action is available through the connected GitHub interface in this session.
- The live Cloudflare Pages → Render integration workflow still requires the repository Actions variables `DASHBOARD_PREVIEW_URL` and `RENDER_BACKEND_URL`. Its actual cross-origin browser smoke test has not run; no repository variables, secrets, CORS rules, or deployment settings were changed.
- No `main` update, PR merge, production/staging deployment, Render configuration/secret change, or CORS relaxation occurred.



## 82. EVM OpenAPI example deprecation fix and current-head CI (2026-11-16)

The feature branch now contains a targeted OpenAPI metadata correction and a regression guard:
- Commit `974247f29542ca9371468d638c2a4b5eab54ce76`: changed the EVM token-index request body's deprecated FastAPI `Body(example=...)` metadata to `Body(examples=[...])`, which places the example in the JSON Schema `examples` array.
- Commit `f0d66921d5858b20195c6503025bc5ea9f69c3e0`: added `test_evm_token_index_body_example_uses_json_schema_examples`, asserting the generated OpenAPI request-body schema contains the expected `examples` array and no deprecated singular `example` key.

**Current-head CI:** Backend and dashboard tests Run #1954:
- Run ID: `43812714921`; job ID: `133117756740`; tested head: `f0d66921d5858b20195c6503025bc5ea9f69c3e0`.
- Job conclusion: **success**.
- Dashboard HTML/script-reference validation: **success**.
- JavaScript syntax validation for `dashboard/app.js`, `dashboard/chart.js`, and `tests/dashboard_live_integration.cjs`: **success**.
- Combined feature-branch Python + Chromium browser QA: **success**, with **687 passed, 1 warning in 10.29s**.
- The separate Python-only step was skipped because the combined feature-branch step ran the test suite.

The FastAPI `Body(example=...)` warning reported in Section 81 is no longer present in this run. The remaining warning is Starlette's `TestClient` / httpx integration deprecation notice, which recommends `httpx2`. No dependency upgrade was made: compatibility and the repository's supported dependency range need a separate review before changing test-client dependencies.

**Evidence boundaries:** This run verifies the current backend/dashboard tree through the repository's combined pytest + Chromium workflow and JavaScript validation. It does not refresh the standalone Node-based 20-test browser workflow or Lighthouse/performance artifact, whose detailed evidence remains tied to the earlier commits identified in Section 79. The live cross-origin Cloudflare Pages → Render smoke test remains unverified because its required Actions repository variables are not configured; no values were created or changed.

**Change control:** No `main` update, PR creation/merge, production or staging deployment, Render configuration/secret change, repository variable change, or CORS relaxation was performed.


## 83. httpx2 test dependency and current-head CI verification (2026-11-16)

The feature branch adds `httpx2>=2.0,<3.0` to the optional `dev` dependency group in `pyproject.toml`. This is a test/development dependency only; production runtime dependencies and `requirements.txt` were not changed.

Current-head Backend and dashboard tests Run #1957:
- Run ID: `43813106020`; job ID: `133118960100`; tested head: `3c209bf5a0983a4ab4cd46c55641fa7b8b82e7e3`.
- Job conclusion: **success**.
- Dashboard HTML/script-reference validation: **success**; both local script references exist.
- JavaScript syntax validation for `dashboard/app.js`, `dashboard/chart.js`, and `tests/dashboard_live_integration.cjs`: **success**.
- Combined feature-branch Python + Chromium browser QA: **success**, with **687 passed in 9.07s**.
- No pytest warnings were printed in this run's test output. This confirms the previous Starlette TestClient/httpx deprecation warning did not recur in this run; it does not claim every warning in every workflow is resolved.
- The separate Python-only step was skipped by workflow design because the combined step ran the complete pytest suite.

**Evidence boundaries and remaining gates:** This current-head run validates the backend/dashboard tree with the combined Python + Chromium tests and JavaScript checks. It does not refresh the standalone Node-based 20-test browser workflow or Lighthouse/performance artifact, whose detailed evidence remains tied to the earlier dashboard source commit identified in Section 79. The live cross-origin Cloudflare Pages → Render smoke test remains unverified because its required Actions repository variables `DASHBOARD_PREVIEW_URL` and `RENDER_BACKEND_URL` are not configured; no values were created or changed.

**Change control:** No `main` update, PR creation/merge, production or staging deployment, Render configuration/secret change, repository variable change, or CORS relaxation was performed.


## 84. Dashboard QA evidence freshness and live-integration gate (2026-11-16)

A Git comparison was performed from the last detailed standalone Dashboard browser/performance QA source commit `008bfe9e5ae9caefee260085d6a57389a664f1e5` to the current feature-branch head before this documentation update, `9b6c224684f71ed18dc4e4de39b311512b9589c0`.

- The comparison reports 9 commits ahead and 0 behind.
- Changed files across those commits: `backend/app/main.py`, `docs/DASHBOARD_QA_AUDIT.md`, `pyproject.toml`, `tests/test_advanced_derivatives_analysis_api.py`, and `tests/test_dashboard_chart.js`.
- No files under `dashboard/` changed in this range. Therefore the dashboard application source used by standalone browser QA Run #60 and performance QA Run #41 remains byte-for-byte unchanged through the current feature head. The standalone QA harness files are also not listed among the changed files.
- This comparison supports carrying forward the prior standalone browser/performance evidence for the unchanged dashboard source; it does not constitute a fresh rerun of either workflow on the new commit.

The latest live integration workflow Run #27 (ID `43812701904`) was also inspected by job:
- `Live URL configuration check`: success; it reported the required repository Actions variables were missing.
- `Live cross-origin Chromium smoke test`: **skipped**.
- Consequently, the workflow's overall success must not be interpreted as a successful live Cloudflare Pages → Render browser test.

The live integration gate remains: configure the exact HTTPS repository Actions variables `DASHBOARD_PREVIEW_URL` and `RENDER_BACKEND_URL` in GitHub repository settings, then rerun/trigger the live workflow through an authorized workflow trigger. No secrets, variables, CORS rules, or deployment settings were changed in this audit.

**Change control:** No `main` update, PR creation/merge, production or staging deployment, Render configuration/secret change, repository variable change, or CORS relaxation was performed.


## 85. Latest feature-branch CI run #1958 verified (2026-11-16)

The feature branch head `65a635ea773be752188695b3476ffe18469a45db` was verified against Backend and dashboard tests Run #1958:

- Run ID: `43813602493`; job ID: `133120512068`; conclusion: **success**.
- Dashboard HTML validation confirmed the expected document and both local script references.
- JavaScript syntax checks passed for `dashboard/app.js`, `dashboard/chart.js`, and `tests/dashboard_live_integration.cjs`.
- The combined feature-branch Python + Chromium browser QA step completed successfully.
- Full pytest output: **687 passed in 12.15s**.
- The separate Python-only step was skipped by workflow design because the combined step ran the complete suite.
- The job had populated steps and retrievable logs; this is actual runner execution evidence, unlike the earlier billing-blocked runs documented in Sections 11–17.

**Remaining evidence gates:** This run does not refresh the standalone Node-based 20-test browser workflow or Lighthouse/performance artifact. The live Cloudflare Pages → Render integration test remains unverified: its workflow's required Actions variables `DASHBOARD_PREVIEW_URL` and `RENDER_BACKEND_URL` have not been configured, so the live cross-origin browser job was skipped in the previously inspected Run #27. A successful general CI run is not a successful live integration run.

**Change control:** This update records CI evidence only. No `main` update, PR creation/merge, production or staging deployment, Render configuration/secret change, repository variable change, or CORS relaxation was performed.


## 86. Governance-branch QA continuation and current evidence (2026-11-19)

The dashboard workstream now continues on `feat/institutional-dashboard-task-governance`, created from the previously verified dashboard feature-branch source commit `e9d89e2014c5298093a3c9b88f6727657663c21f`. The governance branch's changes are limited to governance/documentation, workflow branch filters, and one test-fixture correction. The comparison against `feat/institutional-dashboard-design` shows 16 commits ahead and 0 behind; no `dashboard/**` runtime file or `backend/app/**` runtime source file changed in that comparison.

**Backend + dashboard CI — current full-suite result**
- Run #1969, run ID `44443701895`, tested commit `750b2c64ded70b3504e2cb51206fb7022837d457`: **success**.
- The full Python + Chromium pytest step completed with **687 passed in 11.89s**.
- Dashboard HTML/script-reference validation and JavaScript syntax checks passed.
- The separate Python-only step was skipped by workflow condition because the combined feature-branch step ran the full suite once.
- An earlier run on commit `612c0054049bc93eeb8d8fdf6c3da53cdbab7816` had 686 passed and one failure in `tests/test_news_intelligence.py::test_collect_news_marks_items_unverified_and_reports_coverage`. The fixed RSS fixture date was older than the test's seven-day window, so the service correctly returned no fresh item and the test indexed an empty list. Commit `750b2c64ded70b3504e2cb51206fb7022837d457` changes only that test fixture: its service-level fake provider now supplies a timestamp relative to the test clock. No backend runtime source was changed for this correction.

**Dashboard frontend checks**
- Run ID `44443339378`, commit `a9cf7066c39cf3a27f5de9a34b3349746841393b`: **success**.
- 110 dashboard contract tests and 9 accessibility contract tests passed (119 total); chart fixtures and JavaScript syntax checks passed.

**Standalone Chromium browser QA**
- Run ID `44443343939`, commit `5c93d29bb9d2950378cf24d2a16c14f28553845e`: **success**.
- **20 passed, 0 failed, 0 skipped**. The run used the isolated Chromium browser QA workflow; it is automated browser evidence, not a physical-device or live-backend test.

**Dashboard performance QA**
- Run ID `44443349312`, source commit `1ef19349364abd0cedad7b4044c5fb1bfee2ab56`: **success**.
- Three local simulated-mobile Lighthouse reports (390 × 844) scored **100, 99 and 100** for Performance. FCP samples: **904, 1,363 and 905 ms**; LCP: **1,504, 1,705 and 1,505 ms**; TBT: **0 ms** in all three; CLS: **0.0000238, 0 and 0.0000238**. The performance preset does not provide an Accessibility category score.
- CPU-throttled 1,000-row mocked scanner fixture:
  - 1× CPU: render **67 ms**, sort **39 ms**, search **169 ms**, pagination **69 ms**, five repeated cycles **2,385 ms**, post-GC heap delta **78,108 bytes**, DOM delta **+5**.
  - 4× CPU: render **101 ms**, sort **91 ms**, search **182 ms**, pagination **142 ms**, five repeated cycles **3,293 ms**, post-GC heap delta **63,336 bytes**, DOM delta **+2**.
  - Twelve sampled in-app navigation actions closed the sidebar as expected; no browser page errors were recorded.
- Raw artifact ID: `14492516424`; SHA-256: `05ef76b8063e903be0f5d5f74264459f6ed22c3d6e71c05f75f0ea1585e72a32`.
- These results use a local static QA server and deterministic mocked data. They do **not** establish production network performance, Cloudflare transfer/compression behavior, physical-device performance, long-session memory stability or absence of a long-term memory leak. The dashboard runtime files were unchanged in the subsequent governance/test-only commits, but the performance run's exact tested source commit remains `1ef193...`.

**Live integration gate**
- Run ID `44443354893` completed at workflow level, but its `Live cross-origin Chromium smoke test` job was **skipped**.
- The configuration job explicitly reported missing repository Actions variables `DASHBOARD_PREVIEW_URL` and `RENDER_BACKEND_URL`. The live workflow also requires the approved QA bearer-token secret.
- Therefore Cloudflare Pages → Render live integration is **not verified**. No Actions variables/secrets, Render settings, CORS allowlists or deployment settings were created or changed.

**Change control**
- No `main` update, PR creation/merge, production or staging deployment, database change, production secret change or trading/execution capability change was made.
- The new dashboard governance branch has its own workflow branch filters so backend/dashboard, frontend, browser, performance and live-integration workflows can run there. The live workflow's successful configuration check must not be described as a successful live integration test.


## 87. Dashboard static-asset branch CI and browser verification (2026-11-20)

The isolated branch `fix/backend-dashboard-static-assets` was verified at commit `91f9f838fa23d365d54f5bf270ec8c9c15a64dcf`.

**Backend + Dashboard CI**
- Run ID: `44775319606`; job ID: `136423532206`; conclusion: **success**.
- Dashboard HTML validation: **success**; 2 script references and 1 stylesheet reference were validated.
- Dashboard JavaScript syntax validation: **success**.
- Python test suite: **684 passed in 4.93s**; no failures.

**Standalone Chromium browser QA**
- Run ID: `44775319567`; job ID: `136423451505`; conclusion: **success**.
- Node browser harness: **21 passed, 0 failed, 0 skipped**.
- The new regression test verifies that the 1-second chart timeframe is enabled for Spot, disabled for USD-M and COIN-M, and that switching from Spot while 1s is selected safely resets the selected timeframe to 1m.

**Asset access and API authentication contract**
- The branch test `tests/test_dashboard_asset_routes.py` verifies `/dashboard`, CSS, and JavaScript assets return successfully without browser Bearer authentication, while an unauthenticated `/api/v1/research/phase-readiness` request remains HTTP 401.
- This is automated TestClient evidence for the branch implementation; it is not a live deployment or external-browser test against a hosted backend.

**Integration and change-control limitations**
- The live Cloudflare Pages → Render integration workflow was not part of these two runs. Live cross-origin integration remains unverified until the approved preview/backend URLs and QA credentials are available and the live smoke test actually executes.
- A fresh comparison of `main` against this branch reports a divergent history (732 commits ahead, 1 behind; merge base `527afbb3f2aff7c76db32fb3593302e2cc3ccab5`) and a broad 42-file comparison. The ahead count reflects the branch's full history relative to that merge base; it must not be described as 732 newly added static-asset commits. Integration therefore requires a deliberate, separately reviewed scope/branch strategy rather than a direct merge.
- No `main` update, PR creation/merge, production or staging deployment, database change, secret/configuration change, or CORS relaxation was performed.


## 88. Main-branch Dashboard integration dependency audit (2026-11-20)

A read-only source comparison was completed between `main` and `fix/backend-dashboard-static-assets`. No files on `main` were changed.

**Existing main-branch behavior**
- `backend/app/main.py` already defines `GET /dashboard` and serves `dashboard/index.html`.
- `Dockerfile` is byte-for-byte identical on `main` and the asset branch and already copies both `backend/` and `dashboard/` into the image.
- However, `main` does not contain `dashboard/app.js`, `dashboard/chart.js`, or `dashboard/app.css`. Its current `dashboard/index.html` is a different, larger inline document. Replacing that HTML with the feature-branch document without adding the static mount and three assets would leave its referenced files unavailable.

**Dashboard API compatibility**
- The feature-branch Dashboard JavaScript contains seven explicit API path references: Spot scan, USD-M scan, COIN-M scan, market evidence, market-data quality, research preflight, and research phase readiness.
- All seven corresponding route handlers exist on `main`; a source-level extraction comparison found those seven handler blocks byte-for-byte identical between `main` and the asset branch.
- This is a static source comparison, not a live HTTP compatibility test. Runtime behavior, response payloads with live providers, and hosted deployment behavior still require integration testing.

**Backend changes relevant to a future integration**
- Required to serve the new separate frontend assets: add the branch's `StaticFiles` mount at `/dashboard-assets`, and carry over `dashboard/index.html`, `dashboard/app.js`, `dashboard/chart.js`, and `dashboard/app.css` as one coherent set.
- The existing `/dashboard` route can remain; its current path already resolves to the Dashboard HTML file.
- For a Dashboard hosted on a different origin (for example, a Pages preview calling a separately hosted API), the exact frontend origin must be explicitly allowed through the branch's strict CORS configuration. Same-origin access through the backend's `/dashboard` does not require cross-origin CORS. No origin or secret value was configured during this audit.
- The branch also adds `1s` to Spot and USD-M Kline API interval validation. The Dashboard browser regression test enables the 1s timeframe only for Spot and disables it for both Futures markets. The main-branch Spot Kline route does not yet accept `1s`; therefore, if the Spot 1s chart control is retained in a main-based integration, the Spot interval contract change and its regression test are required. The USD-M API acceptance is a separate backend capability; the current UI intentionally does not expose that interval for USD-M. COIN-M remains unsupported for 1s.

**Integration decision**
- A direct merge of the existing feature branch is not a safe integration method: the branch history is divergent and its comparison with `main` spans 42 files, including unrelated governance, documentation, tests, workflow, and API changes.
- The lowest-risk next implementation path is a fresh integration branch based on current `main`, followed by a narrowly scoped port of the Dashboard asset set, static mount, approved CORS behavior only if cross-origin hosting is chosen, and the required Spot 1s API contract. The seven Dashboard API handlers do not need to be copied because they are identical on both branches.
- Creating that new branch or changing repository refs is deferred pending explicit authorization. No branch was created, no commit was made to `main`, and no PR, merge, deployment, database, secret, or hosted configuration was changed.


## 89. Dashboard connection and cross-origin security contract (2026-11-20)

A focused source review of the feature-branch Dashboard HTML/JavaScript and CORS tests confirmed the following integration requirements:

- The Dashboard does not silently assume a backend URL or token. The user must enter a Backend Base URL and Bearer Token and explicitly test the connection.
- The frontend rejects non-HTTPS remote backend URLs; HTTP is accepted only for localhost, 127.0.0.1, and [::1].
- API requests send the Bearer token in the Authorization header, set `credentials: "omit"`, and use `cache: "no-store"`. The UI also provides an explicit credential-clear action.
- Consequently, when the Dashboard is served from a separate origin, the backend's CORS allowlist must contain the exact HTTPS origin of that frontend. The backend CORS contract allows only GET/POST and Authorization/Content-Type headers, does not allow browser credentials, and rejects unlisted origins.
- The feature-branch CORS suite contains 11 focused tests covering origin parsing, preflight behavior, missing/invalid/valid Bearer credentials, empty allowlists, disallowed methods, and disallowed headers. The backend CI suite passed at commit `91f9f838...`; these tests were included in that 684-test result.
- No actual frontend URL, backend URL, Bearer token, repository Actions variable, or secret was added or exposed during this source audit.

**Deployment implication:** A same-origin Dashboard served at `/dashboard` can call its backend without cross-origin CORS. A Cloudflare Pages frontend calling a separate backend requires an explicitly approved origin and an executed live cross-origin smoke test before claiming integration success.


## 90. Dashboard API request/response contract review (2026-11-20)

A read-only review traced the Dashboard's request construction and response handling against the current `main` route definitions and service implementations.

**Candle chart contract**
- `dashboard/chart.js` selects one of the Spot, USD-M, or COIN-M Kline routes, sends `interval` and `limit=1000`, and requires a JSON object containing a `klines` array before rendering.
- The three `main` Kline handlers return the expected top-level `status`, `source`, `symbol`, `interval`, `count`, and `klines` fields. This confirms source-level response-shape compatibility for supported intervals.
- The chart client offers `1s` among its supported timeframe values, but the current `main` Spot, USD-M, and COIN-M route interval Literals do not accept `1s`. The feature branch intentionally gates the 1s UI control to Spot and carries the required Spot interval contract change. A main-based port must include that Spot-only API change and its regression test; otherwise selecting 1s will receive validation failure. USD-M and COIN-M remain unavailable for 1s in the UI.

**Market evidence contract**
- The Dashboard calls `GET /api/v1/analysis/market-evidence/{symbol}`, accepts only a JSON object, and displays the returned `summary`/ `status` plus the full evidence payload.
- The current `main` route delegates to `build_market_evidence_snapshot`; its tests cover completed/incomplete evidence sections and explicitly assert `NO_TRADE_DECISION`, null buy/sell signal, and null probability.
- The frontend correctly treats this endpoint as an evidence summary, not as candle data. The candle chart is loaded independently from the Kline endpoints.

**Market-data quality contract**
- The quality form sends `market`, `symbol`, `interval`, and `lookback_hours`. Its interval choices match the backend route's allowed interval set; its lookback validation matches the backend's 1–2160 hour bound.
- The backend quality engine reports stored-data availability, freshness, coverage and collector status. Its tests explicitly distinguish `NO_DATA`, `DEGRADED`, `STALE`, and `NOT_MEASURABLE`; a successful HTTP response must not be interpreted as proof that live streams are healthy or complete.
- The Dashboard currently renders the quality report as structured JSON, so no undocumented response-field assumptions were found in this path.

**Evidence classification**
- This review is static source inspection plus review of existing unit tests. It is not a live HTTP test against Binance, a running backend, Cloudflare Pages, or Render.
- No code, `main`, PR, deployment, database, secret, or hosted configuration was changed. The integration-branch approval gate recorded in section 88 remains in force.
