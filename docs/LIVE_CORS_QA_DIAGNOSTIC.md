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
