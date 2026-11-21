# Live CORS QA diagnostic — 2026-11-21

## Finding

A read-only review of `backend/app/main.py`, `backend/app/config.py`, `tests/test_cors_configuration.py`, and `tests/dashboard_live_integration.cjs` identified a false-negative risk in the live CORS assertion.

The browser test performed a cross-origin `fetch()`, received HTTP 401 for a deliberately invalid Bearer token, and then read `Access-Control-Allow-Origin` using `response.headers.get()` inside page JavaScript. The CORS-safelisted response-header list does not include `Access-Control-Allow-Origin`; the server's current `Access-Control-Expose-Headers` policy exposes only `X-Request-ID`. Therefore JavaScript can receive a valid CORS response while `response.headers.get("access-control-allow-origin")` returns `null`. See MDN's documentation for [Access-Control-Expose-Headers](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Access-Control-Expose-Headers), [Fetch API cross-origin requests](https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API/Using_Fetch), and [CORS-safelisted response headers](https://developer.mozilla.org/en-US/docs/Glossary/CORS-safelisted_response_header).

A cross-origin Fetch response resolving with status 401 and type `cors` demonstrates that the browser accepted the CORS response sufficiently to expose its status/body. The exact network response header should be inspected through Playwright's browser-automation response object, not through the page's filtered Fetch `Headers` object.

## Test-only corrections

1. `tests/dashboard_live_integration.cjs` now checks the browser-visible response status, `response.type === "cors"`, and JSON error envelope. It separately captures the actual OPTIONS and GET responses through Playwright and checks the exact `Access-Control-Allow-Origin` value using `response.allHeaders()`.
2. `tests/test_cors_configuration.py` now asserts that the invalid-Bearer HTTP 401 response also carries the exact allowed-origin header.

These changes are test-only. No backend runtime code, CORS allowlist, secrets, repository variables, Render configuration, Cloudflare configuration, database, `main`, PR merge state, or deployment was changed.

## Validation status

- Live test harness update commit: `ffe4cda009891b47065f89894a45fa3e6f747297`.
- Invalid-token unit-test assertion commit: `d57cdb9f02b0180645b30232355fbb8dae8bd3d8`.
- The updated live test file was read back from GitHub; the old page-JavaScript `probe.allowedOrigin` assertion is absent and the Playwright network-header assertion is present.
- No completed post-change CI or live Chromium run has yet been verified for these commits. The changes remain **pending execution**, not PASS.
- The configured Cloudflare Pages Preview and Render backend must still be the intended endpoints for any live result. A successful test against one configured origin does not prove a different preview deployment is configured correctly.

## Next validation

Run the backend/dashboard suite (including `tests/test_cors_configuration.py` and the JavaScript syntax check) and the live integration workflow. Inspect the actual job steps/logs. A live pass must show: OPTIONS 200 with the exact origin, GET 401 for the invalid token with the exact origin, browser Fetch response type `cors`, and no browser page errors. Keep the authenticated-positive request out of scope unless a dedicated QA token is separately authorized and stored as a masked Actions secret.


## Retest result — 2026-11-21

The latest corrected harness was executed successfully.

- Live Integration QA run **#42**, run ID **44846865707**, job **136668614596**: **success**.
- Dashboard origin: `https://7e74d124.universal-binance-ai-backend.pages.dev`.
- Backend origin: `https://universal-binance-ai-backend-staging-qa.onrender.com`.
- Invalid Bearer GET: HTTP **401**, Fetch response type **cors**, JSON payload object.
- Captured actual GET response header `Access-Control-Allow-Origin`: exact Dashboard origin.
- Explicit OPTIONS preflight: HTTP **200**, exact allowed origin.
- Browser page errors: **0**.
- Authenticated positive check: not run; no separately scoped QA credential was supplied for this test.

The first failing assertion was a test-observation issue: page JavaScript could not read the non-safelisted response header. The corrected Playwright harness inspects the actual network response and a direct OPTIONS probe, and now passes against the configured live endpoints. This confirms the tested origin's unauthenticated CORS/preflight path; it does not establish authenticated API success or coverage of every route.

Backend/Dashboard CI run **#2125**, run ID **44846865588**, also passed on commit `3cdd8626c202f8d661203a3a2408b485ed8e4587` with **711 passed in 6.75s**. The feature-branch full Chromium suite was skipped in that workflow; separate Browser QA #87 recorded 29 passed.

No backend runtime code, CORS allowlist, Render or Cloudflare configuration, secrets, database, production deployment, `main`, PR merge state, or trading/order behavior was changed.
