# Dashboard Implementation Progress

**Repository:** `mamunfb/universal-binance-ai-backend`  
**Frontend branch:** `feat/institutional-dashboard-design`  
**Current source checkpoint before this ledger update:** `f051c46f26ea58744a57412917d3438ec854a837`  
**Backend changes:** None in this branch.

## Completed in this work session

- Added `docs/DASHBOARD_DESIGN_SPECIFICATION.md` with the approved dense, expanded-sidebar, advanced-chart design and all requested research domains.
- Added `docs/DASHBOARD_API_CAPABILITY_MAP.md` to separate verified routes from unverified/planned features.
- Replaced the old dashboard page with a dark institutional terminal shell and expanded navigation.
- Added `dashboard/app.css` for the responsive visual system.
- Added `dashboard/app.js` for navigation, in-memory backend connection settings, safe JSON rendering, request timeouts and supported API calls.
- Added `dashboard/chart.js` for OHLCV candlesticks, volume bars, descriptive indicators and strict 3h aggregation from complete UTC-aligned 1h candles.
- Updated Spot scanner default to request all quote assets when its optional quote filter is blank.
- Corrected Spot scanner table fields to match the inspected backend response contract.
- Restricted the Data Quality timeframe selector to the interval values accepted by the inspected backend route.
- Added `tests/test_dashboard_contract.py` for static frontend contract and safety checks.

## Verification performed

- JavaScript syntax compilation for `dashboard/app.js`: PASS.
- JavaScript syntax compilation for `dashboard/chart.js`: PASS.
- HTML ID reference scan: 72 IDs found; no missing IDs referenced through the app's ID helper.
- Script load order check: chart module loads before application module.
- Branch comparison against `main`: frontend/dashboard docs/test files only; no backend Python, migrations, workflows, secrets or deployment files changed.
- Spot scan route and response fields checked against the backend source at the inspected `main` baseline.
- Spot, USDⓈ-M and COIN-M kline route signatures checked against the backend source.

## Additional implementation — scanner interaction pass

- Added client-side sorting to the Spot, USDⓈ-M and COIN-M result tables. Numeric-looking values sort numerically; other fields sort case-insensitively with numeric-aware text ordering.
- Added bounded 100-row pagination to each scanner table, with Previous/Next controls and an explicit matching-versus-returned row count.
- Changed Spot search to filter the complete returned in-memory result set before pagination, rather than hiding only currently rendered DOM rows.
- Added accessible `aria-sort` state to sortable column headers.
- Extended the static contract tests to assert scanner sorting, pagination and full-result filtering hooks.

## Verification status for this pass

- GitHub Contents API confirmed both file updates were committed on `feat/institutional-dashboard-design`.
- The new Python assertions have **not** yet been executed; they are test coverage added, not a passing test result.
- No live scan payload, browser interaction, performance/virtualization or accessibility run was performed. Pagination limits DOM rows to 100 at a time, but the full response remains in browser memory.
- No backend files, CI workflows, database files, secrets or deployment settings were changed. No PR, merge or deployment was performed.

## Additional implementation — candle data and chart calculation hardening

- Candle parsing now rejects null/empty/boolean numeric fields, non-finite values, invalid timestamps, negative volume and impossible OHLC relationships; valid rows are sorted chronologically.
- Extracted explicit timeframe-to-exchange-interval and market-to-kline-route mappings, with unsupported markets rejected before a request is made.
- Corrected flat-price RSI behaviour to return neutral 50 when average gains and losses are both zero.
- Replaced the simple-average true-range label with a Wilder-smoothed ATR(14) calculation and named the output `atr_14_wilder`.
- MACD is now explicitly represented as the EMA(12)-minus-EMA(26) line; signal and histogram are clearly unavailable rather than implied.
- Added Node built-in test-runner fixtures covering malformed candle rejection, chronological parsing, complete/incomplete/duplicate/misaligned 3h buckets, timeframe/route mapping, flat RSI, Wilder ATR and insufficient indicator history.
- Extended the Python static contract suite to assert the fixture suite and chart validation safeguards exist.

## Verification status for chart hardening

- Source and test files were committed through GitHub on the frontend branch.
- The Node fixture suite and Python contract suite have **not** been executed. No test-pass claim is made.
- No live Binance/backend candle payload or browser chart rendering was tested.
- No backend or deployment configuration was changed.

## Additional implementation — advanced Coin Analysis chart workspace

- Expanded the price chart to show an EMA20 overlay over actual OHLCV candlesticks and volume bars.
- Added separate responsive indicator panes for Wilder RSI(14), MACD line, MACD signal (EMA9 of the MACD line), MACD histogram and Wilder ATR(14).
- Indicator series are aligned to the loaded candle array; unavailable warm-up periods remain gaps rather than fabricated zero values.
- Updated the primary **Run Analysis** and Coin Analysis refresh actions to load the selected market/symbol/timeframe candle workspace. Market Evidence remains a separate explicit action.
- Added a monotonically increasing chart request sequence so a slower response from an earlier timeframe selection cannot overwrite a newer selection.
- Added Node fixtures for indicator-series alignment and MACD histogram arithmetic, plus Python static assertions for pane rendering, stale-response protection and primary action wiring.

## Verification status for this pass

- Chart, app, CSS and test updates were committed to the frontend branch.
- Eight Node fixture cases are present in the chart test file; neither the Node nor Python test suite has been executed.
- No live backend data, real browser rendering, cross-device layout or accessibility run has been performed.
- Chart overlays/panes are client-side descriptive calculations, not validated backend signals. ADX, Stochastic RSI, Volume Profile, support/resistance and backend-derived levels are still not implemented in this chart workspace.
- No backend, CI workflow, database, secret, deployment or production hosting files were changed.

## Follow-up refinement — MACD pane consistency

- The Coin Analysis technical summary now reports the latest computed MACD line, EMA9 signal line and histogram values, matching the separate chart panes.
- Extended the MACD fixture to assert that all three latest values are finite when sufficient history is present.
- The chart test suite now contains eight named Node test cases; execution is still pending.


## Additional implementation — advanced indicator and volatility-band pass

- Added a candle-aligned Wilder ADX(14) series with directional-movement and true-range smoothing; the first ADX value is aligned to candle index 2n−1 and the warm-up remains unavailable rather than being filled with zero.
- Added Stochastic RSI with explicit %K and %D smoothing and bounded 0–100 output; flat RSI windows use a neutral 50 value.
- Added aligned Bollinger Bands (20, 2) upper/middle/lower series using population standard deviation, and rendered all three as overlays with EMA20 on the price chart.
- Expanded the chart's price scale to include the Bollinger band range so the overlay is not clipped when it extends beyond candle highs/lows.
- Added three Node fixture cases covering Bollinger alignment/math, ADX and Stochastic RSI warm-up/range handling, and insufficient history.
- These remain descriptive chart indicators only; they are not validated trading signals or recommendations.

## Verification status for advanced indicator pass

- Source and fixture changes were committed on the frontend-only branch.
- The Node and Python test suites have **not** been executed in a repository runtime. The new fixtures are coverage added, not passing test results.
- Browser rendering, live backend data, accessibility and mobile QA remain unperformed.
- No backend source, migrations, CI workflows, secrets, deployment settings, PR, merge or deployment were changed.


## Additional implementation — USDⓈ-M and COIN-M scanner controls

- Added independent full-response client-side symbol search fields to the USDⓈ-M and COIN-M scanner pages; filtering occurs before the existing 100-row pagination.
- Added returned-row counts for both futures scanners.
- Added scan coverage summaries for Spot, USDⓈ-M and COIN-M using recognized top-level response fields: returned rows, status, eligible, scanned, failed, matched, source and timestamp.
- Missing backend metadata is explicitly displayed as "Not supplied"; returned-row count is not misrepresented as exchange-wide coverage.
- Preserved Spot's matching-versus-returned count when scan metadata is refreshed.
- Extended static contract coverage for scanner controls and advanced ADX, Stochastic RSI and Bollinger indicator panes.

## Verification status for scanner-controls pass

- App, HTML and test changes were committed to the frontend-only branch and read back from GitHub.
- Static test assertions have been extended; the Node and Python suites have **not** been executed locally or in CI.
- No real scan response has been used to confirm optional coverage fields; absent fields remain clearly labelled "Not supplied".
- No backend, migration, CI, secret, deployment, PR, merge or production changes were made.


## Additional implementation — scanner search and coverage completion

- Added independent full-response symbol search to USDⓈ-M and COIN-M scanners; search is applied before the existing 100-row pagination.
- Added returned-row counts and coverage summaries to Spot, USDⓈ-M and COIN-M pages.
- Coverage summaries display recognized response fields only: returned rows, status, eligible, scanned, failed, matched, source and timestamp.
- Missing response metadata is labelled "Not supplied"; returned rows are not represented as total exchange coverage.
- Preserved Spot's matching-versus-returned count during coverage refresh.
- Extended static contract checks for all three scanner coverage blocks, futures search controls, and advanced ADX/Stochastic RSI/Bollinger indicators.

## Verification status for scanner-controls pass

- App, HTML and test changes were committed and read back from the frontend-only branch.
- Static test assertions were added but have **not** been executed locally or in CI.
- No live scan response has verified the optional coverage fields; absent fields remain labelled "Not supplied".
- No backend, migration, CI, secret, deployment, PR, merge or production changes were made.

## Not yet verified / remaining work

- The Python dashboard contract test file has been added but has not yet been executed in CI or a repository test runner.
- No browser-based visual, keyboard, mobile, accessibility or cross-browser test has been run.
- No live backend connection or real authenticated API response has been tested from this frontend.
- Scanner sorting, 100-row client-side pagination and full-response search are implemented for Spot, USDⓈ-M and COIN-M; server-side pagination/virtualization is not available. Coverage summaries show only recognized returned fields and label missing metadata as Not supplied.
- Coin Analysis now renders OHLCV candlesticks, volume, EMA20 and Bollinger(20,2) overlays, plus separate RSI, Stochastic RSI, ADX, MACD and ATR panes. It is still not a full TradingView-equivalent chart; Volume Profile, support/resistance and backend-derived structure levels remain outstanding.
- The 3h frontend aggregation requires exactly three consecutive 1h candles aligned to UTC bucket starts; incomplete buckets are discarded. Fixture cases exist but have not been executed.
- Daily scheduler, 96 scans/day, AI selection/research reports, three historical modes, Neon+R2 archive query, comparison, full news/on-chain views, signal evaluation and complete risk pages remain unintegrated or capability-unverified.
- API auth/CORS behaviour and production frontend hosting are not verified.
- No PR was opened, no merge was performed and no deployment was triggered.

## Safety boundary

This branch is frontend-only. Do not add backend changes here. Do not add trading/order/withdrawal controls. Do not persist backend credentials in browser storage. Do not enable planned pages until their API schemas and tests are verified. Do not deploy or merge without explicit approval.

## Next implementation sequence

1. Run the new static tests in the repository environment and add a frontend CI check without changing backend runtime behaviour.
2. Add fixture-based tests for candle parsing, timeframe mapping and 3h bucket completeness.
3. Complete scanner table fields, sorting/filtering and explicit coverage/failure display for all three markets.
4. Continue Coin Analysis chart QA, including price-band overlay alignment and indicator fixtures.
5. Integrate only verified existing analysis, order-flow, derivatives, news and on-chain endpoints.
6. Finish page scaffolds with explicit Unavailable/Planned status where backend support is missing.
7. Browser QA and accessibility/mobile checks.
8. Create a reviewable frontend-only PR. Backend gap work remains a separate subsequent task.


## Test-discovery correction

- Code review found that two scanner coverage test methods had been placed after the module-level `unittest.main()` guard and therefore were not part of the test class during normal direct execution.
- Moved both methods into `DashboardContractTests` before the main guard. GitHub readback confirms both methods now precede the guard.
- This is a test-discovery/source correction only. The Python and Node test suites have still **not** been executed; no passing test result is claimed.
- No backend, CI workflow, migration, secret, deployment, PR or merge action was performed.


## Batched chart data-quality and indicator regression pass

- Hardened numeric parsing so whitespace-only strings are rejected instead of being coerced to numeric zero.
- Candle parsing now removes every row associated with a duplicated open timestamp. This avoids silently treating duplicate exchange rows as separate sequential candles and prevents duplicate rows from contaminating indicator calculations.
- Added Node regression fixtures for whitespace-only numeric values, duplicate timestamps and flat-market behaviour (neutral Stochastic RSI %K/%D and zero ADX after warm-up).
- Extended the Python static contract suite to assert the new parser guards and regression fixtures exist.
- The Python contract test file's scanner coverage tests were also moved before the `unittest.main()` guard in the preceding correction, so direct execution can discover them.

## Verification status for batched chart pass

- All changes were committed on `feat/institutional-dashboard-design` and are limited to dashboard chart source, dashboard tests and this progress ledger.
- GitHub source readback is the verification performed so far. Node and Python test suites have **not** been executed in a repository runtime; no test-pass claim is made.
- No live exchange payload, browser rendering, mobile/accessibility test, CI workflow, PR, merge or deployment was performed.


## Dashboard HTML contract expansion

- Extended the HTML parser used by the Python contract suite to record duplicate element IDs, not just the set of IDs.
- Added a regression assertion that the HTML contains no duplicate IDs and that the chart module is loaded before the application module.
- This strengthens static structural checks for DOM binding stability and script dependency order; it does not replace browser QA.
- Test execution remains pending because no repository-local runtime or authorized CI run has been used in this session.


## Follow-up correctness and scanner metadata pass

- A deeper source review caught a control-flow defect in the duplicate-candle hardening: the parser returned the sorted array before executing its duplicate-timestamp count/filter block. Reworked the parser to assign the validated/sorted rows to `parsed`, then execute and return the unique-timestamp filter. This makes the prior duplicate-timestamp regression fixture exercise the intended behavior.
- Hardened scanner count extraction: whitespace-only strings, booleans, non-finite values and negative counts are no longer treated as valid coverage counts. Missing/invalid metadata remains explicitly unavailable rather than being shown as zero.
- Added Python static contract tests asserting duplicate filtering is reachable in the parser and scanner count parsing rejects invalid metadata.
- These are source and static-test changes only. Node/Python suites remain unexecuted in a repository runtime; no pass result is claimed.


## Additional static-test review — parser assertion scope

- Reviewed the chart and scanner source against the current frontend contract tests.
- Corrected the Python contract test's parser-body extraction delimiter so the duplicate-timestamp reachability assertion isolates the `parse()` function rather than accidentally scanning the remainder of the file.
- This tightens the regression test's scope; it does not change dashboard runtime behaviour.
- The Node and Python suites have still **not** been executed. This is a source/test review and GitHub readback only; no pass result is claimed.
- No backend files, CI workflows, secrets, database or deployment settings were changed. No PR, merge or deployment was performed.


## Batched chart request invalidation and selection-consistency pass

- Added an explicit chart-request invalidation method so an in-flight candle request cannot overwrite the workspace after the user changes the market, symbol or timeframe.
- The chart view is cleared and marked as awaiting analysis when market/symbol/timeframe controls or scanner market selection changes; this avoids presenting old candles as if they belonged to the new selection.
- Market Evidence now invalidates pending candle requests and clears the previous candle chart because that endpoint does not provide OHLCV chart data.
- Renamed the technical chart action to a market-neutral label; the handler already uses the currently selected market rather than always requesting Spot.
- Extended the Python static contract suite to assert the invalidation hook and its app integration.
- GitHub source writes and subsequent readback are the verification performed. Node and Python tests have **not** been executed; no pass result is claimed. Browser QA and live API testing remain outstanding.
- Changes remain confined to dashboard frontend source, dashboard tests and this ledger. No backend, migrations, CI workflows, secrets, deployment settings, PR, merge or deployment were changed.


## Scanner and analysis concurrency / numerical consistency pass

- Added a request-sequence guard to market scans. Older responses (including late failures) are ignored after a newer scan starts or the selected market changes, preventing stale scanner results from overwriting the current market view.
- Hardened table sorting so blank strings and booleans are not treated as numeric zero/one values; numeric sorting is used only when both compared values are valid finite numbers.
- Added a separate market-evidence request sequence. Changing the analysis selection or starting a candle-chart load invalidates pending evidence responses; superseded chart/evidence responses no longer show success as if they were current.
- Candle API failures from obsolete chart requests are suppressed as superseded rather than surfaced as current-selection errors.
- Added a numerical fixture comparing the latest RSI and ATR series values against the compact indicator snapshot, plus static contract assertions for scanner/evidence/chart request invalidation and safe sorting.
- Changes and tests were written to the frontend branch and source readback remains required. Node.js and Python suites have **not** been executed; no test-pass claim is made. Browser QA and live API integration remain outstanding.
- No backend runtime, migrations, workflows, secrets, database or deployment configuration changed. No PR, merge, CI trigger or deployment was performed.


## Technical-indicator deterministic reference fixtures

- Added a monotonic one-directional OHLCV fixture that checks Wilder ADX warm-up alignment and the expected 100 reading once the directional-movement ratio is fully directional.
- Added exact Stochastic RSI %K/%D warm-up-index assertions for the configured 14/14/3/3 periods.
- Added a reproducible 20-value Bollinger population-standard-deviation reference fixture (mean 10.5; population variance 33.25) and checks for both bands.
- Extended the static dashboard contract suite so these numerical fixtures cannot silently disappear.
- These are test additions only; they have not been executed in this environment. Numerical correctness beyond these deterministic invariants remains subject to runtime test execution and independent reference comparison.


## Scanner table accessibility, sorting and API response hardening

- Scanner column headers now support keyboard activation (Enter/Space), expose sort labels and preserve the column's aria-sort state. Pagination status is announced through a polite live region and Previous/Next controls have explicit accessible labels.
- Sorting now places missing values last in either direction, sorts valid numeric values numerically, keeps numeric and text values in deterministic groups, and uses symbol as a stable tie-breaker.
- API request timeout values are validated as positive finite numbers. Request bodies are detected by undefined-ness rather than truthiness, so valid falsy JSON payloads are not silently dropped. Successful empty responses are rejected explicitly instead of leaking null into response renderers.
- Added static contract assertions for the new API guards, keyboard sorting, accessible pagination and mixed-type deterministic ordering.
- Changes are committed and source/test/ledger readback has been verified from the branch. No runtime test execution or browser accessibility audit has been performed in this environment.

- Accessibility follow-up: sortable headers retain native table-column header semantics rather than being re-role'd as buttons; they remain keyboard-focusable with Enter/Space handling and explicit key-shortcut metadata. Contract assertions enforce this.


## Data-quality concurrency and backend URL validation pass

- Added a dedicated data-quality request sequence. If the user changes market, symbol, interval or lookback while a report is pending, the old response (or late failure) is ignored and the UI asks for a fresh check instead of displaying stale data as current.
- Changing backend connection settings and clearing credentials invalidates pending scanner, quality and analysis/evidence work so old-connection responses cannot overwrite the current session's view.
- Backend URL configuration now parses the URL and rejects embedded username/password, query parameters and fragments in addition to requiring HTTPS for remote hosts (HTTP remains limited to localhost/127.0.0.1).
- Added static contract assertions for quality request invalidation and URL credential/query rejection.
- Source/test readback verification is pending. Node.js/Python suites and browser testing have not been run; no runtime pass is claimed.


## Health/evidence request races and mobile scanner usability

- Health checks now have their own request sequence. A delayed health response or failure from a previously configured/cleared backend is ignored instead of changing the current connection status.
- Market-evidence failures are suppressed when that evidence request has already been superseded by a newer selection or analysis action.
- Editing the Spot quote-asset filter invalidates an in-flight Spot scan and labels the coverage area so results from the previous filter are not mistaken for current results.
- Scanner table cells normalize null and empty values to the same unavailable marker rather than displaying literal "null" or an empty cell.
- Mobile scanner pagination now wraps cleanly at narrow widths, provides touch-sized controls, and sortable headers expose a visible keyboard-focus outline.
- Added static contract assertions for health/evidence/Spot-filter request races, null-cell normalization and responsive pager styles. Source/test/ledger readback verification is pending; no runtime test or browser QA has been performed.


## Scanner sorting performance and API error-surface hardening

- Scanner sort now decorates filtered rows once with the selected value, parsed numeric value, missing-value flag and symbol; the comparator no longer reparses values or constructs a locale comparator for every comparison. One reusable numeric-aware `Intl.Collator` handles text and symbol ordering. Missing values remain last in both sort directions and pagination/counts use the sorted result set.
- Non-success API responses now display only bounded, whitespace-normalized string details (maximum 300 characters) after control-character removal. Structured error payloads fall back to an HTTP-status message instead of dumping arbitrary backend objects into the UI.
- Added static contract assertions for decorated scanner sorting, collator reuse and bounded/sanitized API error details. The sanitizer expression was read back after correction. Runtime tests and browser performance profiling have not been run.


## Scanner pagination cache, mobile keyboard navigation and API failure review

- Scanner filtering/sorting now caches the computed filtered and sorted row set by row-array identity, query, sort key and sort direction. Previous/Next pagination reuses the cached order and slices only the visible page; a new scan, search query or sort selection invalidates the cache. This removes repeated full-dataset sorting during page navigation while preserving sorting and filtering semantics.
- Mobile navigation now exposes its expanded state and controlled sidebar relationship to assistive technology. Opening the menu moves focus into navigation; Escape closes it and restores focus to the menu button; selecting a navigation link closes the sidebar and resets expanded state.
- Added visible focus treatment for navigation and primary dashboard controls. At narrow phone widths, top-bar controls switch to a two-column grid to reduce horizontal pressure.
- Fetch failures surfaced as browser/network TypeErrors now receive a clear connection message, distinct from AbortController timeout errors. Non-idempotent requests are not automatically retried; the current dashboard API helper has no retry loop. A future retry policy should be limited to explicitly idempotent requests and transient failures, with a bounded attempt count and backoff.
- Added static contract assertions for scanner cache reuse, mobile menu state/Escape behavior and distinct timeout/network error messaging.
- Validation status: source changes and test/documentation updates have been written to the feature branch. Runtime Node/Python suites, synthetic scanner benchmark, browser keyboard audit and responsive viewport QA have not yet been run. The local repository clone could not be obtained because this execution environment could not resolve github.com; no CI workflow was triggered.


## Local test environment preparation notes

- Repository dependency metadata was reviewed: Python requires 3.11 or newer; development extras include pytest, pytest-asyncio and Ruff. The root requirements file lists the application runtime dependencies.
- Recommended local setup from a clean clone:
  `python -m venv .venv`
  `source .venv/bin/activate` (Windows PowerShell: `.venv\\Scripts\\Activate.ps1`)
  `python -m pip install --upgrade pip`
  `python -m pip install -e ".[dev]"`
  `python -m pytest`
- The dashboard chart fixture suite uses Node's built-in test runner and can be invoked with `node --test tests/test_dashboard_chart.js`; the dashboard contract checks are included in the Python pytest suite.
- This execution session has Node.js 22 and Python 3.13 available, but a GitHub clone attempt failed at DNS resolution for github.com. Therefore dependencies were not installed and neither suite was executed. These commands are setup guidance, not a claim of passing tests.
