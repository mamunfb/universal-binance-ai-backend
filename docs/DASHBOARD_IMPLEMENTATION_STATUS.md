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


## Navigation current-page semantics

- The active sidebar link now exposes `aria-current="page"`; inactive links have the attribute removed on each navigation change. This complements the mobile menu's expanded/collapsed state and Escape-key focus restoration.
- Added a static contract assertion for current-page semantics. Browser screen-reader verification remains pending.


## Follow-up regression coverage — scanner search and request boundaries

- Extended the dashboard contract suite to assert that scanner search resets pagination and that the sorted-row cache is keyed by the active search query.
- Added static checks that API requests omit ambient browser credentials, disable response caching, and preserve valid falsy request bodies by checking body presence against `undefined`.
- Added static checks that superseded candle-chart requests ignore both late successful responses and late failures.
- These checks improve regression coverage but remain source-level assertions. The Python and Node test suites have not been executed in this session; no passing result is claimed.
- No retry loop was introduced: scanner and analysis endpoints have not been proven safe for automatic retries, and repeated scans could create unnecessary backend load. No CI, PR, merge or deployment was triggered.


## Responsive stylesheet integrity correction

- A source-level review found two literal backslash-`n` sequences embedded in `dashboard/app.css` before the chart-caption and indicator-pane rules. These are not CSS line breaks and can cause the following selector token to be parsed incorrectly.
- Replaced both escaped sequences with actual newline characters, restoring the selectors as independent CSS rules.
- Added a Python contract assertion that rejects literal backslash-`n` tokens and requires the chart-caption and indicator-pane selectors to begin on real new lines.
- GitHub readback is the only verification performed. The browser stylesheet parser/rendering has not been exercised; no browser QA or runtime test is claimed.


## Large-batch chart regression fixtures

- Added deterministic Node fixtures that feed 10,000 reversed OHLCV rows through the candle parser, including a duplicated timestamp, and assert sorted unique output.
- Added a 3,000-hour fixture covering 1,000 complete UTC-aligned 3h buckets, plus a missing-hour case that must discard only the incomplete bucket.
- Extended the Python static contract suite to require both scale-oriented fixtures and load the Node fixture source explicitly.
- These are large-input correctness/regression fixtures, not measured performance benchmarks. Node/Python tests have not been executed here; no runtime or speed result is claimed.


## 3h aggregation close-time integrity

- Tightened the UTC-aligned 3h aggregation guard: all three source rows must now have the exact hourly close timestamp (`openTime + 3,599,999 ms`) as well as consecutive hourly open timestamps.
- Added a Node regression case that corrupts one source candle's close timestamp and requires the entire 3h bucket to be discarded.
- Added a Python static contract assertion for both the production guard and its regression fixture.
- This closes a malformed-source-row acceptance gap; it does not validate exchange connectivity or replace runtime tests. Node/Python suites remain unexecuted in this session, and no test-pass claim is made.


## Deterministic EMA, Wilder RSI and ATR reference fixtures

- Added a short EMA reference sequence that checks the initial simple-average seed and each subsequent recursive smoothing step.
- Added a compact Wilder RSI fixture with hand-calculated gain/loss averages, covering the initial overbought result and subsequent smoothed updates.
- Added an OHLC fixture with true ranges of 2, 4 and 6, checking the ATR seed of 3 and next Wilder-smoothed value of 4.5.
- Extended the Python static contract suite to require these independent numeric fixtures.
- These fixtures are authored but not executed in this environment. The numerical values were derived directly from the test inputs and formulas; runtime test status remains unverified.


## Scanner refresh pagination consistency

- Source review found that replacing a scanner dataset invalidated the cached filtered/sorted rows but retained the previous page index. When a new scan returned fewer rows, the page was merely clamped to the last available page, which could leave the user on a later page rather than showing the refreshed dataset from its beginning.
- New row-array identity now resets the page index to zero while invalidating the sorted-row cache.
- Added a Python contract assertion for the reset and for the comparator's missing-value ordering branch. The missing-value branch returns before applying ascending/descending direction, preserving missing values at the end in either sort direction.
- GitHub source readback is the verification performed. Runtime Python/Node tests and browser interaction tests remain unexecuted; no passing test claim is made.


## Scanner numeric sort input-type hardening

- Tightened numeric sorting so only finite JavaScript numbers and non-empty numeric strings are treated as numeric values.
- Boolean, array and object values are no longer coerced through JavaScript's `Number(...)` conversion (for example, an empty array or a single-element array can otherwise become a numeric value). Such malformed field values now use the text-sort path instead.
- Added a Python static contract assertion for the primitive-type guard and numeric-string parsing.
- This is source-level hardening; runtime sort behaviour and browser interaction have not been executed in this session. No runtime test-pass claim is made.


## Scanner response row-shape validation

- Scanner response arrays are now filtered to non-null, non-array object records before table rendering; nulls, primitive values and nested arrays are excluded rather than displayed as misleading table rows.
- The coverage metadata reports the number of malformed rows excluded, and an informational scan notification calls attention to that count without treating a partially usable response as a complete scan failure.
- Added a Python static contract assertion for the filter, rejected-row count and user-visible reporting.
- This is defensive frontend response handling, not a claim that the backend response schema has been fully validated. GitHub readback is the only verification performed; runtime tests and browser QA remain unexecuted.


## Scanner count metadata type hardening

- Source review found that JavaScript numeric coercion could treat non-numeric container values (such as empty arrays or single-element arrays) as numbers when extracting eligible, scanned, failed or matched counts.
- Count extraction now accepts only non-negative safe integers supplied as number primitives or non-empty numeric strings. Fractional values, booleans, arrays, objects, blank strings, negative values, NaN, infinities and integers outside JavaScript's safe-integer range are rejected as missing metadata.
- Updated the Python static contract to require the primitive-type guard and finite/non-negative check.
- GitHub source readback is the only verification performed; Python/Node runtime tests and browser QA remain unexecuted.


## Scanner top-level response shape validation

- Scanner endpoints now require a non-null JSON object at the top level. Arrays and primitive JSON values are rejected before scan summaries, metrics, coverage metadata or result tables are updated.
- The validation error explicitly notes that previously displayed results are preserved, avoiding a misleading empty scan view when the backend returns the wrong payload shape.
- Added a Python static contract assertion that verifies validation occurs before summary rendering.
- This does not define or fully validate every backend field; it protects the frontend boundary while retaining the existing flexible response-field mapping. GitHub readback is the only verification performed; runtime tests and browser QA remain unexecuted.


## Scanner missing-result-array observability

- Source review found that the previous array helper returned an empty list both when the backend explicitly supplied an empty result array and when no recognized result-array field existed. Those cases were indistinguishable in the UI and both could appear as a successful empty scan.
- Scanner handling now identifies which recognized result field (symbols, markets, results or data) actually contains an array. An explicitly empty array remains a valid empty result; a missing array is called out in the coverage metadata and produces an informational notice.
- The coverage panel records the selected result field, while malformed row filtering and rejected-row counts remain in place.
- Updated Python static contract checks cover the missing-versus-empty distinction. GitHub readback is the only verification performed; runtime tests and browser QA remain unexecuted.


## Scanner market selection validation

- Scanner requests now accept only the three supported market identifiers: SPOT, USD_M and COIN_M.
- Unsupported values are rejected before the request sequence or selected market state is changed, preventing accidental fallback to the COIN-M endpoint for an unknown market value.
- Added a Python static contract check that requires validation to precede request-sequence mutation.
- This is source-level validation only. GitHub readback is the verification performed; runtime tests and browser QA remain unexecuted.


## Scanner refresh freshness and retained-result states

- When a scan begins, the overview status indicates that a refresh is in progress and that previously rendered results are being retained.
- A current-request network/API failure changes the status to `Refresh failed · previous results retained`; an invalid top-level payload uses `Invalid response · previous results retained`.
- A successful response replaces the previous summary and rows through the existing render path. Superseded requests do not overwrite the status for a newer request.
- This is a user-visible lifecycle indicator, not a measured data-age guarantee. Backend timestamps remain displayed only when supplied by the backend.
- Added a static contract test for refresh-state ordering and retained-result messaging. Runtime tests and browser QA remain unexecuted.


## Missing scanner result array preserves previously rendered rows

- A response object that omits all recognized result-array fields (`symbols`, `markets`, `results`, `data`) no longer clears the currently rendered scanner table. The UI still reports that no recognized result array was supplied and records the response metadata.
- An explicitly supplied array, including an empty array, remains authoritative and replaces the table contents. This keeps a valid empty scan distinct from an incomplete response shape.
- Added static contract assertions that all three market tables are rendered only when a recognized result array is present.
- GitHub source readback is the verification performed; runtime tests and browser QA remain unexecuted.


## Incomplete scanner responses preserve summary freshness

- Result-array detection now occurs before rendering scan summary metrics. When a response object contains no recognized result array, the dashboard retains both the previous table rows and the previous summary metrics/timestamp.
- The scan status explicitly reports `Incomplete response · previous results retained`; response-level coverage diagnostics still update and the informational notice remains.
- A response containing an explicit array (including `[]`) remains authoritative and updates the summary and table.
- Added static contract assertions for this ordering and status behavior. Runtime tests and browser QA remain unexecuted.


## Scanner secondary result-array observability

- The scanner keeps the established primary result-array precedence (`symbols`, `markets`, `results`, `data`) and continues to use the first recognized array as the authoritative row set.
- If the response also contains other recognized array fields, their names are now listed separately in the coverage metadata as `Additional array fields`. This makes alias overlap visible without silently merging potentially duplicated datasets or changing the selected rows.
- Added static contract assertions for secondary-field discovery, metadata display and argument wiring.
- GitHub source readback is the verification performed; runtime tests and browser QA remain unexecuted.


## Scanner display metadata primitive validation

- Scanner status, source and timestamp labels now accept only non-empty strings or finite numeric values. Objects, arrays, booleans, empty strings and non-finite numbers fall back to an explicit `Not supplied`/contextual fallback label rather than rendering generic object text or misleading values.
- Status and timestamp aliases continue to use the existing precedence, while invalid primary aliases can fall back to a valid secondary alias.
- Count fields retain their separate non-negative safe-integer validation.
- Added static contract assertions for the metadata formatter and its use in summary and coverage output. GitHub readback is the verification performed; runtime tests and browser QA remain unexecuted.


## Scanner metadata display length bounds

- Backend-provided status, source and timestamp labels are now length-bounded before display, in addition to the existing primitive-type checks.
- Status text is capped at 80 characters, source text at 120 characters and timestamp text at 80 characters; longer values are visibly truncated with an ellipsis. This prevents unexpectedly large metadata strings from overwhelming compact summary and coverage areas.
- Numeric metadata remains limited to finite numbers, and invalid types continue to use the configured fallback. Raw API payloads remain available in the existing response inspection paths where applicable.
- Added static contract assertions for truncation behavior and field-specific limits. GitHub source readback is the verification performed; runtime tests and browser QA remain unexecuted.

## Health, quality and market-evidence metadata hardening

- Health status and Data Quality report status now use the shared primitive-only metadata formatter with an 80-character display limit. Backend objects, arrays, booleans, blank strings and non-finite numbers no longer become misleading generic text in these compact status labels.
- Market-evidence summaries now use the same safe formatter with a 120-character limit and fall back to a safely formatted status value before the static explanatory message.
- Raw health, quality and evidence payloads remain available in their existing response/state inspection paths; this change only constrains compact UI labels.
- Added Python static contract assertions for the three display paths. GitHub source readback is the verification performed; Python/Node runtime suites and browser QA have not been run.

## Scanner count alias conflict diagnostics

- Scanner coverage now checks all recognized aliases within each existing eligible, scanned, failed and matched count group. When two or more valid non-negative safe-integer aliases in the same group disagree, the coverage line reports the field names and supplied values.
- The established primary-alias precedence and displayed metric values are unchanged; conflicting aliases are not added together, averaged or silently substituted. Invalid count values remain excluded by the existing count validator.
- This is a diagnostic for inconsistent response metadata, not an assertion that different count groups must satisfy a particular arithmetic relationship.
- Added a Python static contract assertion for conflict detection and preservation of the existing count extraction path. GitHub source readback is the verification performed; runtime tests and browser QA have not been run.

## Scanner metadata alias provenance

- Scanner coverage now identifies which recognized status, source and timestamp field supplied the displayed metadata. Status precedence remains `status` then `scan_status`; timestamp precedence remains `generated_at`, then `timestamp`, then `updated_at`; source currently reports the supplied `source` field.
- Provenance is determined using the same primitive-only metadata acceptance rule as the displayed value. Invalid or blank higher-priority aliases do not appear as the selected field.
- Timestamp values are deliberately displayed as supplied (with the existing length bound); the dashboard does not guess whether numeric values represent seconds, milliseconds or another unit, and does not reinterpret timezone-less strings.
- Added a Python static contract assertion for the selected source and timestamp field labels. GitHub source readback is the verification performed; runtime tests and browser QA have not been run.

## Evidence and quality request error recovery

- A current Market Evidence request failure now changes the chart/evidence status to an explicit failure state and displays a bounded error summary. The previously rendered evidence JSON is not cleared.
- A current Data Quality request failure now reports that the previous report is retained and appends a bounded error summary. The previous report output is not cleared.
- Superseded request failures remain ignored and cannot replace the status for a newer selection/request.
- Health connection error labels are now length-bounded before display. Error strings remain rendered as text, not HTML.
- Added Python static contract assertions for the evidence, quality and health error paths. GitHub source readback is the verification performed; runtime suites and browser QA have not been run.


## Market evidence refresh preserves the previous report

- Corrected the Market Evidence loading path so it invalidates stale candle-chart state without calling the broader view reset that cleared the evidence JSON output.
- While a new evidence request is pending, the prior evidence payload remains visible and the status explicitly says it is retained. A successful current response replaces the payload; a current failure leaves it intact and reports a bounded error. Superseded requests remain unable to update the view.
- Added a static contract assertion for the loading state, chart-only invalidation and success-only payload replacement ordering.
- GitHub readback is the verification performed; Python/Node runtime suites and browser QA have not been run.


## Technical chart request lifecycle and contract-test discovery correction

- Technical chart refreshes now expose a loading state that explicitly retains the previous chart. A current request failure reports a bounded error and says the previous chart is retained; the chart, raw analysis output and last successful analysis are not cleared by the failure path.
- The application-level request sequence now guards both late successful responses and late failures. A superseded chart request returns without changing the newer selection's status or stored analysis.
- During a follow-up audit, several recently added dashboard contract test methods were found below the module's `unittest.main()` guard. They were therefore not part of the `DashboardContractTests` class and would not be discovered as intended. The methods have been moved back into the test class before the single main guard, and a source-level regression check now verifies their placement.
- Added a static contract assertion for the technical chart loading, retained-result failure and superseded-request paths.
- GitHub source readback is the verification performed. Python/Node runtime suites and browser QA have not been run; no test-pass claim is made.


## Overview refresh attempts health and scanner independently

- Corrected the Overview refresh action so a failed `/health` request no longer prevents the selected market scanner request from being attempted.
- Health and scanner requests now settle independently. Each endpoint continues to update its own loading/success/failure state and retain its previous data on failure; if one or both fail, the refresh action reports a bounded partial-failure summary after both requests settle.
- Added a Python static contract assertion for the independent request execution and bounded failure summary.
- GitHub source readback is the verification performed; runtime tests and browser QA have not been run.


## Superseded connection tests cannot report success

- The Settings connection-test action now checks the health request result before writing its success message. If the health request was invalidated by a newer health check or by clearing/changing connection settings, it exits without claiming the backend responded successfully.
- Added a Python static contract assertion that the superseded-result guard precedes the success status update.
- GitHub source readback is the verification performed; runtime tests and browser QA have not been run.


## Health, Quality and Spot quote-filter refresh states

- Health refresh now explicitly indicates that the previous health status is retained while the latest health request is pending; a current failure still reports Unavailable and a bounded connection error.
- Quality refresh now explicitly says the previous report is retained while the requested symbol and interval are loading. The prior report output is only replaced after a current successful response.
- Changing the Spot quote filter invalidates any in-flight scanner request and now updates the scanner status as well as coverage text, making clear that previous results remain and a new scan is required.
- Added static contract assertions for these three lifecycle states. GitHub source readback is the verification performed; runtime tests and browser QA have not been run.


## Backend and market changes clear stale loading indicators

- Applying new backend connection details invalidates in-flight work and resets the health indicator to Not checked; the connection indicator no longer carries forward a success state from the previously configured backend.
- Clearing credentials resets health, scanner and quality states so an invalidated request cannot leave a misleading loading label or an old backend status on screen.
- Changing the scanner market through either market tabs or the default-market setting now replaces an invalidated scan loading state with an explicit instruction to run a new scan.
- Added static contract coverage for backend reconfiguration, credential clearing and market-selection invalidation. These checks are source-level assertions; runtime tests and browser QA remain outstanding.


## Health and Data Quality response-shape validation

- A successful HTTP response is no longer treated as a healthy backend unless `/health` returns a non-null JSON object; arrays and scalar JSON values are rejected and reported as unavailable.
- Data Quality accepts only a non-null JSON object. A successful HTTP response containing an array or scalar is reported as invalid, and the previously displayed report is preserved.
- Added static contract tests verifying validation occurs before health state is marked successful or quality output is replaced. Runtime tests and browser QA have not been run.


## Candle response and timestamp validation

- Chart loading now rejects successful API payloads unless the top-level response is a non-null JSON object and `klines` is an array. Invalid payloads produce a clear error before the chart renderer can replace the previous chart.
- Candle parsing now requires safe-integer timestamps within the JavaScript Date range for both open and close times. This prevents out-of-range timestamps from reaching `toISOString()` and breaking an otherwise successful chart render.
- Added Node regression cases for invalid response shapes, missing `klines`, unsafe integers and out-of-range timestamps. These tests were added but have not been executed in this environment.


## Chart selection and concurrent-load safety

- Chart market, timeframe and symbol inputs are now validated before a request sequence is allocated. An invalid selection therefore cannot supersede a valid chart request already in progress.
- The chart loader accepts only the dashboard-supported timeframe set and requires a non-empty string symbol before constructing the API path.
- Added regression cases for invalid selections, ensuring they do not issue API calls or invalidate a pending valid request; for a newer failed request superseding an older response; and for malformed candle batches being rejected before render.
- These are source and test-fixture changes only; Node tests and browser QA have not been executed.


## 3h candle aggregate numeric safety

- Three-hour aggregation now checks the summed source-candle volume after aggregation. If individually finite source volumes overflow to a non-finite total, that bucket is discarded rather than passing Infinity into chart scaling and indicator calculations.
- Added a Node regression fixture using finite maximum-range volume values to exercise aggregate overflow rejection. This test was added but not executed.


## VWAP volume-overflow safety

- Replaced direct total-volume and price-volume accumulation with a normalized, incremental weighted mean. This avoids overflowing the raw sum when individual finite candle volumes are very large while retaining volume-weighted typical-price semantics.
- Added a regression test with two maximum-range finite volumes and distinct typical prices; the corrected fixture uses typical prices 11 and 23, so the expected VWAP is 17. The test was added but not executed.

## Indicator-series and chart-rendering extreme-value safety

- Replaced direct arithmetic means in the EMA/SMA, RSI warm-up and ATR warm-up paths with incremental weighted means, avoiding overflow from summing many individually finite values.
- Bollinger deviation now operates on values normalized by their maximum absolute magnitude. A band is left unavailable (null) if its mathematically derived bound cannot be represented as a finite JavaScript number; the compact indicator snapshot follows the same rule.
- RSI and ATR series now stop publishing values after an unrepresentable intermediate result rather than exposing Infinity or NaN.
- Indicator-pane and candlestick-chart vertical coordinate calculations now normalize the value domain before calculating spans, avoiding an infinite max - min span for finite values with opposite signs.
- Added Node regression fixtures using Number.MAX_VALUE-scale OHLCV values and an unrepresentable Bollinger bound. These tests were added but have not been executed. GitHub source readback is the only verification performed; runtime tests and browser QA remain outstanding.

## ADX and chart-overlay extreme-value handling

- ADX true-range and directional-movement inputs are normalized by their shared finite maximum before Wilder accumulation. This preserves the directional ratios while preventing otherwise finite per-candle movements from overflowing their rolling sums.
- Candlestick overlays now render separate SVG polylines across contiguous finite runs. Unavailable Bollinger/EMA points are treated as gaps instead of being filtered out and accidentally joined across missing intervals.
- Added an ADX regression fixture with maximum-range finite price values whose unnormalized directional-movement sums would overflow. The test was added but has not been executed. GitHub source readback remains the only verification performed.

## Signed indicator-axis rendering regression coverage

- Updated the indicator-pane zero reference line to use the same normalized coordinate transform as the plotted series. This avoids relying on an unscaled range span that can overflow for finite values of opposite signs.
- Added a chart-load regression fixture that exercises rendering with signed MACD values and its zero baseline. The test was added but not executed; no runtime or browser verification is claimed.

## MACD and Stochastic RSI boundary hardening

- MACD line, signal and histogram outputs now explicitly reject non-finite intermediate results. An unrepresentable histogram point is emitted as unavailable (`null`) rather than allowing Infinity or NaN into the chart series.
- Stochastic RSI now validates all four period/smoothing arguments as positive safe integers and rejects unsafe combined lookback lengths. Invalid or non-array input returns correctly sized empty/unavailable series instead of throwing or producing invalid values.
- Added regression fixtures for extreme finite MACD input, invalid/unsafe Stochastic RSI periods and non-array Stochastic RSI input. These tests were added but have not been executed; runtime and browser verification remain outstanding.

## Indicator input and period validation

- EMA, RSI, ATR and ADX series now reject non-array inputs without throwing and require positive safe-integer periods before allocating or calculating series. Invalid periods return an unavailable (`null`) series of the input length.
- Stochastic RSI also validates the combined K/D smoothing lookback, in addition to its individual periods, preventing unsafe integer arithmetic in its index calculations.
- Added regression tests for non-array inputs and invalid, fractional, negative and unsafe period values across the indicator series APIs. Tests have not been executed; source readback is not a substitute for runtime verification.

## Defensive 3h aggregation input handling

- The exported 3h aggregation helper now safely returns an empty result for non-array input and filters malformed candle objects before grouping. It validates finite OHLCV fields, safe integer timestamps, positive prices, non-negative volume and consistent OHLC bounds before aggregation.
- Added regression coverage for non-array input, malformed candle objects, and a valid three-candle hourly group. These tests have not been executed; runtime verification remains outstanding.

## Candle numeric parsing hardening

- Candle row parsing now accepts finite JavaScript numbers and decimal-form numeric strings (including decimal fractions and scientific notation), while rejecting non-decimal coercions such as hexadecimal/binary/octal strings, booleans, blank strings and non-finite values.
- Added regression coverage for accepted decimal strings, rejected coercions and duplicate open timestamps. Duplicate timestamps continue to invalidate every ambiguous row at that timestamp rather than selecting an arbitrary candle.
- Tests were added but not executed; no runtime or browser verification is claimed.

## Indicator missing-data recovery and alignment

- EMA, RSI and ATR series now treat non-finite inputs/intermediates as segment boundaries. They remain unavailable across the gap, then restart only after a complete fresh warm-up window of consecutive valid observations is available.
- Output arrays retain the same index alignment and length as their input series; no values are shifted across missing observations. This allows later valid chart segments to render without connecting or carrying calculations through invalid data.
- Added regression coverage for EMA, RSI and ATR recovery after gaps. Tests have not been executed; runtime/browser verification remains outstanding.

## ADX, Bollinger and MACD gap alignment

- ADX now calculates independently over contiguous valid candle segments. An invalid OHLC candle breaks the directional-movement history; ADX resumes only after a fresh segment has enough candles for its full Wilder warm-up. Output indices remain aligned with the original candle array.
- Bollinger rolling windows remain unavailable whenever their complete lookback crosses a missing/non-finite observation, then naturally become available again after a full valid window.
- MACD's fast/slow EMA components and signal EMA now inherit the gap-aware EMA behavior. Signal warm-up restarts from the next valid aligned MACD segment, and histogram values remain null unless both aligned components are finite.
- Added regression fixtures for ADX restart, Bollinger rolling-window recovery and MACD signal/histogram alignment after gaps. Tests have not been executed.

## Volume chart scaling edge cases

- Volume bars now scale against the actual maximum volume in the visible candle window. This keeps sub-unit and very small positive volumes visually proportional instead of effectively suppressing them with a hard-coded minimum scale.
- When every visible candle has zero volume, bar heights are explicitly zero; the chart does not divide by zero or emit non-finite SVG attributes.
- Added rendering regression coverage for tiny positive volume values and an all-zero-volume window. Tests have not been executed; browser QA remains outstanding.

## Chart request cancellation and stale-response lifecycle

- The chart module now owns an AbortController for its active candle request. Starting a newer valid chart request aborts the previous request; explicit chart invalidation (for example, a market/symbol/timeframe or backend-connection change) also aborts the active request and advances the sequence guard.
- The dashboard API wrapper accepts an optional caller-provided AbortSignal while retaining its existing request timeout. It removes the external abort listener in `finally` and distinguishes caller cancellation from timeout errors.
- Superseded chart responses remain ignored even if a transport/API implementation does not honor AbortSignal; cancellation is an efficiency improvement, while the sequence check remains the correctness guard.
- Added a regression test that verifies chart invalidation aborts the supplied signal and returns a superseded result. Tests have not been executed; browser/network cancellation behavior remains unverified at runtime.

## Bounded chart payload processing

- Chart loading now caps source candle processing at the latest 1,000 rows, matching the request's configured `limit=1000`. Oversized backend responses cannot cause unbounded sorting, indicator calculation or chart rendering work in the browser.
- The chart result reports both `source_rows_received` and `source_rows_processed`, alongside `candle_count` (which may be lower for 3h aggregation or invalid rows), so truncation and aggregation are distinguishable.
- Added regression coverage using an oversized 1,200-row payload and verifying that only the latest 1,000 source rows are processed. Tests have not been executed; no performance benchmark is claimed.

## Cancellation contract regression coverage

- Updated the dashboard's static contract checks to match the active AbortController lifecycle rather than the former sequence-only invalidation implementation.
- Added source-contract checks for caller-signal forwarding, abort-listener cleanup, cancellation-vs-timeout messaging, active transport abort and retention of the stale-response sequence guard.
- These are source-level assertions only. The Python contract suite and JavaScript chart tests have not been run in this work session.

## Stochastic RSI rolling-window performance

- Replaced repeated per-candle array slicing, min/max scans and smoothing reductions with monotonic deques for rolling RSI extrema plus incremental rolling sums for %K and %D.
- The rolling extrema and smoothing passes are linear in the number of observations rather than repeatedly rescanning each configured window. Missing RSI observations reset the active window and smoothing warm-up, preserving gap alignment and null behavior. Raw %K and smoothed %K/%D are clamped to their documented 0–100 range against floating-point boundary drift.
- Added regression coverage for gap recovery, bounded 0–100 output, existing warm-up indices and equivalence with a straightforward reference implementation. These tests have not been executed; no measured benchmark is claimed.

## ADX input structure validation

- ADX segment detection now requires positive finite high, low and close values with internally consistent high/low bounds around the close. A structurally malformed candle breaks the segment just like a missing or non-finite candle.
- The next valid segment starts a fresh directional-movement and Wilder ADX warm-up; values are not carried across malformed candle boundaries.
- Added regression coverage for an internally inconsistent high/close relationship, including the null gap and exact restart warm-up index. Tests have not been executed.

## ATR input structure validation

- ATR true-range sampling now requires both the current and previous candles to have positive finite OHLC values with internally consistent high/low bounds around each close. A malformed candle and the immediately following transition are excluded so a structurally invalid previous candle cannot seed the next true-range observation.
- Wilder ATR seed collection restarts after the invalid transition and waits for a complete fresh period before publishing values.
- Added regression coverage for malformed OHLC bounds, the invalid transition, and the exact post-gap warm-up index. Tests have not been executed.

## Overflow-safe Wilder smoothing

- Scalar and series RSI/ATR calculations now update Wilder averages as convex weighted terms (`previous × (n−1)/n + current/n`) instead of multiplying the previous average by `n−1` before division. This avoids an avoidable intermediate overflow when the mathematically representable smoothed value is near the JavaScript numeric limit.
- The initial finite-mean seeds and existing gap-reset behavior are retained. Added large-magnitude rising-price/range regression coverage for scalar and series RSI/ATR, plus a source-contract assertion for the stable update form.
- Tests have not been executed; this is a source-level numerical-safety change, not a benchmark claim.

## SVG batching and Bollinger input safeguards

- Candlestick chart SVG elements are now assembled in a detached `DocumentFragment` and appended to the SVG once, rather than mutating the live SVG tree for every grid, candle, volume bar and overlay element. This reduces repeated live-tree append operations; no browser benchmark has been run and no measured speedup is claimed.
- Bollinger series now safely return empty aligned arrays for non-array input instead of throwing while reading `.length`. Invalid period or multiplier parameters continue to return null-filled arrays.
- The default Bollinger window remains a numerically scaled, per-window population-deviation calculation. It is intentionally not replaced with a naïve rolling sum-of-squares algorithm, which can lose precision or overflow on extreme finite inputs. Chart payloads are already capped at 1,000 source rows and the default period is 20, so the current default work is bounded; a more complex rolling algorithm requires a separately validated stable-variance design.
- Added source-level checks and regression coverage for non-array input, invalid parameters and the fragment-based chart builder. Tests have not been executed.

## Chart test harness alignment

- Updated the oversized-payload chart-rendering test double to provide `document.createDocumentFragment()`, matching the SVG batching API used by the production renderer. Added a static contract assertion so both chart-rendering DOM shims retain fragment support.
- This closes a test-fixture compatibility gap introduced by the SVG batching refactor; the test suite remains unexecuted under the current work restrictions.

## EMA and incremental-mean extreme-value safety

- Added a scaled convex blend helper for finite weighted averages. It normalizes both inputs by their largest absolute magnitude before combining them, clamps the normalized convex result to the mathematically valid [-1, 1] interval, then restores the original scale. Invalid operands or weights return null.
- Reused the helper in incremental `finiteMean`, scalar EMA and EMA series updates. This avoids avoidable intermediate overflow when averaging same-sign finite values close to `Number.MAX_VALUE`, while preserving the intended weighted-average/EMA recurrence.
- Added regression coverage for constant and alternating values near the numeric limit and for the compact dashboard indicator snapshot. Tests have not been executed; no benchmark or runtime result is claimed.

## Analysis request cancellation on navigation

- Leaving the Coin Analysis page now invalidates its active evidence sequence and aborts in-flight chart and market-evidence requests. Returning to the page cannot allow a response from the previous visit to overwrite the current analysis state.
- Market-evidence requests now receive an AbortSignal and own a tracked controller. Starting a chart request, changing analysis selections, clearing credentials, or navigating away aborts the pending evidence request; sequence checks remain as a fallback if the transport does not honor cancellation.
- Added static contract checks for navigation invalidation, caller-signal forwarding and controller cancellation. Tests have not been executed.

## Keyboard navigation and accessible page transitions

- Navigating between dashboard sections now moves keyboard focus to the destination page's primary heading when navigation was initiated from an existing focused control. The heading receives `tabindex=-1` so it can receive programmatic focus without entering the normal Tab sequence; initial page startup does not steal focus from the document body.
- Decorative glyphs inside sidebar navigation links are marked `aria-hidden=true`, keeping accessible link names focused on their text labels.
- Added explicit visible focus styling for input, select and textarea controls, while suppressing the default outline on the programmatically focused page heading.
- Added source-level contract checks for focus movement, decorative icon hiding and focus-visible styles. No browser or screen-reader QA has been performed; tests have not been executed.

## Scanner table accessibility and pager focus retention

- Named the Spot, USDⓈ-M and COIN-M scanner result tables and exposed each horizontally scrollable wrapper as a keyboard-focusable region. Column headers now declare `scope=col`.
- Added a visible focus indicator to the keyboard-scrollable table regions for narrow-screen users.
- Pagination now restores focus to the corresponding enabled Previous/Next control after rerendering the pager, and each control identifies the table body it controls. If the requested direction becomes unavailable at a boundary, focus falls back to the remaining enabled pager control.
- Added static source-contract coverage for the three named tables, 16 column headers, keyboard-scroll focus styling and pager focus restoration. No browser/screen-reader QA has been performed; tests have not been executed.

## Credential-change cancellation hardening

- Applying a new backend connection or clearing stored-in-memory credentials now calls the shared analysis cancellation path. This invalidates the active analysis sequence, aborts an in-flight chart load, and aborts an in-flight market-evidence fetch instead of merely ignoring its eventual response.
- Health request sequence invalidation remains separate, and scanner/quality invalidation continues to run as before.
- Added a static contract test covering both credential-change paths and the market-evidence abort controller. Tests have not been executed.

## Accessible dynamic status announcements

- Added polite, atomic status live regions for connection state, scanner state, backend health, chart state, technical summary, data-quality state and connection-settings feedback. This allows assistive technology to announce important asynchronous state changes without moving keyboard focus.
- Added source-contract coverage to ensure each designated status element retains its live-region semantics.
- Credential replacement and credential clearing now use the shared analysis cancellation helper, so pending chart and market-evidence requests are actively aborted in addition to being invalidated by sequence guards. Added a static contract for both flows.
- Tests and browser/screen-reader QA have not been executed.

## Mobile navigation and input validation hardening

- Closed mobile navigation is now marked `inert`, preventing hidden sidebar links from receiving keyboard focus. Opening the mobile menu removes inertness and focuses the first navigation link; closing with Escape or selecting a page restores focus to the menu control before hiding the sidebar. Resizing to desktop clears the mobile-open state and restores normal sidebar interaction.
- Data-quality symbol input now requires 1–40 alphanumeric characters, and lookback hours must be an integer from 1 to 2160. Invalid values set a field-specific custom validity message and report it before a request is sent.
- Backend URL input is required and validated as an absolute URL. Remote backends must use HTTPS; HTTP is limited to localhost and 127.0.0.1. Embedded credentials, query parameters and fragments remain rejected.
- Added static source-contract checks for inert sidebar behavior, resize/Escape handling and the validation rules. Runtime tests and browser/mobile QA have not been executed.


## Responsive mobile navigation accessibility

- The mobile sidebar now synchronizes its `inert` state on every viewport resize, not only when resizing to desktop. This prevents off-canvas navigation links from remaining keyboard-focusable after switching from desktop to a narrow viewport.
- The menu control now announces “Open navigation” or “Close navigation” in step with its expanded state. Resizing closes the mobile drawer and restores the closed-state semantics.
- Added a source-contract test for resize synchronization, sidebar inertness and the changing accessible label. Tests and browser/device accessibility checks have not been executed.

## Backend URL validation feedback

- Invalid or missing backend base URLs now set a field-level custom validity message and call the browser validity reporter before the connection attempt is rejected. This makes HTTPS, absolute-URL, host and prohibited URL-component errors discoverable at the input rather than only through a transient toast.
- Editing the URL clears the stale custom validity state; clearing credentials also resets the URL field validity.
- Added a source-contract assertion for validation feedback, input reset and credential-clear reset. Runtime tests and browser validation UX have not been executed.


## Credential-change stale-data clearing and Display Preferences

- Applying backend connection settings or clearing credentials now clears connection-scoped dashboard content, not only its status labels. Cached scan/health/analysis references are reset; scanner table rows, search filters, coverage summaries, readiness output, quality output, chart content and technical/evidence output are cleared.
- Existing request sequence invalidation and AbortController cancellation remain in place, so a late response from the previous connection cannot repopulate the cleared view.
- Display Preferences now initialize the active market and timeframe controls on page startup. Changing the default market/timeframe synchronizes the active dashboard controls and invalidates analysis tied to the previous selection.
- The display timezone preference now formats recognized ISO-style scan timestamps through Intl.DateTimeFormat; changing timezone re-renders the cached scan summary and coverage timestamp. Preferences remain page-session-only; no browser storage or backend persistence was introduced.
- Added static regression contracts for connection-scoped data clearing, cached timestamp timezone formatting, and startup/default preference wiring.
- Source readback is the only verification performed for this pass. Runtime tests, browser QA, keyboard/screen-reader testing and responsive viewport testing have **not** been run. No test pass is claimed. No backend source, CI workflow, PR, merge or deployment was changed.


## Research-readiness request race protection

- A final API call-site audit found that the two Research Preflight/Phase Readiness buttons used the shared API helper but did not have request-sequence protection. A response started with old credentials could therefore repopulate the readiness panel after connection data was cleared.
- Added a dedicated readiness request sequence and AbortController. Starting a newer readiness request cancels the previous one; applying or clearing backend credentials aborts and invalidates readiness requests before clearing their displayed output.
- Both readiness actions now use the guarded loader, validate the response as a JSON object, and ignore superseded success/failure results.
- Added a static regression contract for readiness request cancellation, sequence checks and both button handlers.
- Source readback only. Runtime tests and browser QA remain unrun; no pass is claimed. Backend files, CI, PR, merge and deployment remain untouched.


## Scanner and Data Quality request cancellation hardening

- Follow-up request-lifecycle inspection found that scanner and data-quality requests used sequence guards but did not abort the underlying fetch when superseded or when backend credentials changed.
- Added dedicated AbortControllers for both request families. Starting a replacement request aborts the previous request; existing selection and credential invalidation paths now abort in-flight work while sequence guards continue to prevent stale UI updates.
- Request cleanup only clears the active controller when it still belongs to that request, avoiding an older request's finally handler from clearing a newer controller.
- API abort classification now records whether the timeout fired, so a later caller cancellation cannot mislabel an already-triggered timeout (and caller cancellation remains distinct from timeout).
- Added static regression contracts for scanner cancellation, quality cancellation, credential-change invalidation, and timeout/caller-abort classification.
- Source readback only. No runtime tests, browser QA, keyboard/screen-reader checks or responsive device checks were run. No test pass is claimed. Backend source, CI workflows, PR state, merge and deployment were not changed.


## Health request cancellation and compact viewport safeguards

- Health checks now own an AbortController. Starting a replacement health check aborts the previous request; applying a new backend URL/token or clearing credentials aborts the active health request and invalidates its sequence before the connection state is reset.
- The sequence guard remains in place so a late response cannot overwrite the current connection state even if a fetch implementation does not honor cancellation.
- Narrow-screen CSS now constrains flex/grid children and filter controls to their available width, gives filter labels fluid sizing, and adds compact-viewport wrapping rules for screens at or below 360px.
- Added explicit keyboard focus styling for brand/text links and dynamically generated table pager buttons, alongside existing input, navigation, and table-region focus states.
- Added static contract checks for health cancellation on superseding requests and credential changes, plus responsive sizing and focus selectors. These checks have **not** been executed. No browser, mobile-device, screen-reader, or runtime network QA is claimed.
- Frontend-only change: no backend files, CI workflows, PR state, merge, or deployment were changed.


## Market evidence refresh failure-state consistency

- The Market Evidence action no longer replaces the visible chart placeholder or clears the technical summary before the request succeeds. During refresh, the status explicitly says the previous chart and evidence are retained.
- A failed or superseded request therefore leaves the last successfully rendered chart/evidence intact. The chart placeholder is changed to the endpoint-capability explanation only after a current request returns a valid JSON object.
- Invalid response shapes (null, arrays, and primitives) are rejected before the UI's previous evidence is replaced.
- Added a static regression contract for the preservation and validation ordering. It has not been executed; browser/runtime behavior remains unverified.
- Frontend-only. No backend, CI, PR, merge, or deployment changes.


## Scanner incomplete-response and stale-coverage safeguards

- Scanner responses without a recognized result array (symbols, markets, results, or data) now return an explicit incomplete-response status and leave the last successful table, summary, and coverage metadata untouched.
- If a non-empty result array contains no valid object rows, the response is rejected before replacing the prior successful scan. A genuinely empty array remains a valid empty scan result; mixed valid/malformed arrays render valid rows and report the rejected-row count.
- Successful Spot scan coverage now includes the requested quote-asset filter so the displayed coverage is easier to reconcile with the visible query.
- Added static regression contracts for incomplete payload preservation, all-malformed-row rejection, and quote-filter coverage labeling. These tests have not been executed; runtime behavior remains unverified.
- Frontend-only change. No backend source, CI, PR, merge, or deployment changes.


## Scanner query-provenance stability

- The last successful scan now retains its requested Spot quote filter as part of the cached scan metadata, rather than re-reading the current input control during display refresh.
- Timezone/display-preference refresh now renders the scan summary with the market that produced the cached response, not the currently selected market.
- Scanner coverage refresh reuses the quote-filter value captured when that successful request was made. Changing the selected filter or market therefore cannot relabel the previous successful scan during a timestamp refresh.
- Added a static regression contract for market and quote-filter provenance across display refreshes. The test has not been executed; browser behavior remains unverified.
- Frontend-only. No backend source, CI, PR, merge, or deployment changes.


## Scanner numeric sorting edge-case correction

- The scanner sorter previously applied ascending/descending direction to the mixed numeric/non-numeric comparison. As a result, a malformed value such as a non-empty text placeholder could move ahead of valid numeric values when sorting descending.
- The comparator now keeps missing values last and keeps non-numeric values after valid numeric values in either direction; direction is applied only when comparing values of the same sortable class.
- Updated the existing source-contract assertions to match the current abortable scanner request and cached sorting implementation, and added a regression contract for malformed numeric values in both directions.
- Static source assertions were inspected after the edits; the Python test suite was not executed and browser behavior remains unverified.
- Frontend-only. No backend source, CI, PR, merge, or deployment changes.


## Scanner duplicate-symbol diagnostics

- Scanner coverage metadata now reports the number of unique non-empty symbol strings, the number of distinct symbols appearing more than once, and the number of extra duplicate rows.
- Symbol comparison trims surrounding whitespace and normalizes case for diagnostics. Rows are intentionally retained in the scanner table; this frontend does not silently deduplicate market data or assume that similarly named assets across different market contexts are interchangeable.
- Duplicate diagnostics are computed once per metadata render and do not alter the backend response or the table's row set.
- Added a source-contract regression test for the diagnostic counts and row-retention path. The Python test suite has not been executed; browser/runtime behavior and large-dataset performance remain unverified.
- Frontend-only. No backend source, CI workflow, PR state, merge, or deployment was changed.


## Scanner malformed cell-value rendering

- Scanner table cells now render null, undefined and empty values as an em dash; non-finite numeric values, malformed numeric strings, and non-string/non-number types in price/volume/change columns are shown as "Invalid number".
- Object and array values are shown as "Invalid value" rather than the unhelpful JavaScript string "[object Object]". Boolean and ordinary text values remain readable.
- Cell content continues to be assigned through `textContent`; no backend payload is inserted as HTML.
- Added a source-contract regression test for malformed numeric and structured values. The Python test suite has not been executed; browser/runtime rendering remains unverified.
- Frontend-only. No backend source, CI workflow, PR state, merge, or deployment was changed.


## Scanner table DOM insertion batching

- Scanner pagination still renders only the current page (100 rows), and row/cell content remains created with DOM APIs and assigned through `textContent`.
- The current page's rows are now assembled in a detached `DocumentFragment` and appended to the table body once, including the empty-state row. This avoids one live table-body append per row; no measured performance improvement is claimed because browser profiling has not been run.
- Added a source-contract regression check for fragment construction, row accumulation and the single body append. The Python suite has not been executed and large-market browser profiling remains outstanding.
- Frontend-only. No backend source, CI workflow, PR state, merge, or deployment was changed.

## Scanner large-dataset allocation review

- Source inspection found that the first single-array refactor retained a decorated object per matching row in the sort cache. Although it removed intermediate arrays, those per-row objects also retained parsed sort values and symbol strings; this was not a sufficiently conservative memory design.
- Revised the implementation to retain only row references in the filtered/sorted cache. Search pushes matching source-row references into one array, sorting operates directly on that array, and pagination slices only the visible page. The extra incoming-row copy and full-size decorated-object array are avoided.
- The comparator now reads the selected field and parses numeric strings during comparisons. This reduces retained per-row cache metadata at the cost of repeated comparator work; the CPU/memory trade-off is unmeasured and must be checked with browser benchmarks.
- Numeric/missing-value ordering remains explicit: missing values stay last and non-numeric values stay after valid numeric values in both directions. Tie-breaking remains symbol-based.
- Updated the static regression contracts to verify row-reference-only caching and numeric safety. Static contract method count remains 105; tests have not been executed.
- Search remains O(N × searchable columns) per uncached query and sorting remains O(M log M) for M matching rows. No debounce, worker, server-side pagination, or backend changes were introduced.
- This is a source-level memory-allocation design improvement, not a measured RAM or speed result. No heap snapshot, browser profiling, large-dataset benchmark, Python test execution, CI run, merge, or deployment has been performed.
- Frontend-only: backend source and CI workflows remain untouched.



## Scanner search input responsiveness

- Spot, USDⓈ-M and COIN-M search controls now update their normalized query immediately but defer the filter/sort/render pass by 150 ms. Rapid keystrokes cancel the pending render and schedule one pass after typing pauses; the search remains local to the already loaded scanner rows and does not trigger an API request.
- Each scanner table has its own pending timer, so typing in one market does not delay searches in another market. Clearing backend credentials cancels pending scanner search renders while clearing the query and cached rows.
- Added a static source-contract test for debounce scheduling, timer replacement and credential-clear cancellation. The test has not been executed; the delay and responsiveness have not been measured in a browser.
- This is a frontend interaction change only. No backend source, CI workflow, PR state, merge, or deployment was changed.


## Scanner numeric sort comparison-cost review

- Source review found that the compact row-reference cache avoided retained decorated row objects, but numeric strings were reparsed with Number() on every comparator invocation. For numeric sorting this repeated conversion work can occur O(M log M) times for M matching rows.
- Added a per-sort-pass WeakMap keyed by the original row object. Each row selected sort-key numeric interpretation is computed at most once during that sort pass and reused by later comparisons. The cache is local to the sort operation and does not add persistent per-row metadata to view.sortedCache.
- The comparator still applies missing/non-numeric ordering and direction rules as before. This is a source-level reduction in repeated numeric parsing, not a measured speedup; WeakMap overhead and actual browser performance remain unbenchmarked.
- Replaced the obsolete static test that expected a decorated array with assertions for the WeakMap-based row-reference strategy. The dashboard static contract file now contains 109 test methods; the test suite has not been executed.
- Frontend-only. Backend source, CI workflow, PR state, merge and deployment remain unchanged.


## Scanner repeated-query normalization review

- The filter loop previously converted each searchable field to uppercase again for every new query. Added a per-table WeakMap that stores one normalized searchable-text string per source row, preserving the exact searchable columns and case-insensitive substring behavior.
- The cache is weakly keyed by original row objects, and is replaced whenever a table receives a new row array or connection-scoped scanner data is cleared. It does not retain rows independently or create a decorated row array. It does retain one derived text string for each row still referenced by the table, so memory cost must be measured against reduced repeated string conversion.
- Updated the scanner search contract to reflect debounced rendering and added a static contract for cache reuse and invalidation. Tests have not been executed; no large-dataset speed or memory improvement is claimed.
- Frontend-only. Backend source, CI workflow, PR state, merge and deployment remain unchanged.


## Scanner debounce and immediate-action coordination

- A lifecycle review found that a pending debounced search render could still fire after a user triggered an immediate table render, such as sorting, paging, or a newly completed scan. This could cause an unnecessary second filter/sort/render pass.
- renderRows now cancels and removes that table pending search timer before performing its own render. The debounced callback removes its timer before calling renderRows, so it does not cancel itself. Each table remains independently scheduled.
- Added a static contract for cancellation ordering and updated the documented static test-method count to 108. The Python test suite has not been executed; browser interaction timing has not been tested.
- Frontend-only. Backend source, CI workflow, PR state, merge and deployment remain unchanged.

## Scanner cache invalidation contract

- Strengthened the static contract to verify that each new response-row array updates the active row reference, clears the sorted-result cache, and replaces that table's WeakMap search-text cache in the same invalidation branch.
- This protects against stale cached search/sort results when a later scan returns a new dataset. The scanner currently filters the response into a new row array before rendering; row-object mutation in place is not part of the observed response path.
- Static test-method count is now 109. This is a source-contract update only; tests and browser behavior have not been executed.

## Branch and CI identity clarification

- Repository PR inventory was checked: no pull request currently has `feat/institutional-dashboard-design` as its head or base branch. Therefore the dashboard branch is not currently covered by a PR-triggered workflow run.
- The open draft PR #4 is a separate change: its head is `fix/binance-public-market-data-endpoints`, not this dashboard branch. Its validation claims must not be treated as dashboard-branch validation.
- The latest dashboard commit has no PR-triggered workflow run returned by the commit-workflow lookup, and its combined commit status has no status entries. This means dashboard CI is unverified/not run for the current head, not passing.
- No PR was created, no workflow was dispatched, and no merge or deployment was performed. This entry corrects branch/PR identity ambiguity; it does not change source code or runtime behavior.

## Dashboard contract correction and isolated CI

- Corrected a stale scanner static assertion: filtering now verifies the WeakMap-backed `scannerSearchText(target,item,keys)` helper rather than the removed inline `keys.some(...)` implementation.
- Added a focused contract test for search-text WeakMap creation, per-row cached values, and invalidation of both search and sorted caches when a new response-row array arrives.
- The dashboard contract test file now contains 110 test methods. This is a method count, not a test execution result.
- Added `.github/workflows/dashboard-frontend.yml`, isolated from backend runtime checks. It runs Node syntax checks for `dashboard/app.js` and `dashboard/chart.js`, the Node chart fixture suite, and the Python dashboard contract suite. It triggers on pushes to this dashboard branch and on pull requests targeting `main` when dashboard/test/workflow paths change.
- Workflow execution is pending verification. No backend source, migrations, existing backend CI workflow, secrets, deployment settings, PR state, merge, or deployment were changed.


## Dashboard CI execution follow-up

- The first push-triggered Dashboard workflow run was created, but GitHub reported the job as failed before assigning a runner: the job had no execution steps and no runner ID. A single retry produced the same pre-runner failure.
- Because no runner started and no steps were recorded, neither the Node syntax checks, Node chart fixtures, nor Python contract tests executed. This is an infrastructure/runner-start failure signal; it does not establish that the test code passed or failed.
- Added `workflow_dispatch` so the dashboard workflow can also be started manually, and included this status ledger in both push and pull-request path filters.
- CI remains unverified until GitHub allocates a runner and records the test steps. No backend or deployment configuration was changed; no PR was created, merged, or deployed.

## Dashboard contract audit — stale expectations refreshed

- A further source-to-test review found additional static assertions that still described superseded dashboard implementations, including the former scanner row-copy/sort structure, previous mobile navigation focus handling, earlier metadata fallbacks, and an older scanner response-shape flow.
- Updated the affected contract checks to assert the current implementation: row-reference sorting and cache invalidation, bounded metadata formatting, mobile focus restoration, current scanner result-array validation, chart request sequencing, and the actual CSS selector structure.
- The contract file remains at 110 test methods. A source-level cross-check now finds no remaining direct `assertIn(..., self.js/self.html/self.chart_js/self.css)` literals that are absent from the corresponding current source files. This is static consistency checking only; it does not execute the Python suite or prove runtime behavior.
- The latest workflow run for commit `8e93863a9af8d279c968c1ad456e623bdf939e73` again failed before runner steps were recorded. The latest job returned an empty step list, so Node/Python checks remain unexecuted.
- Frontend tests and documentation only. Backend source, PR state, merge, deployment, and production configuration remain untouched.
