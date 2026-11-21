"use strict";

const { test } = require("node:test");
const assert = require("node:assert/strict");
const { chromium } = require("playwright");

function requiredHttpsUrl(name) {
  const raw = process.env[name];
  assert.ok(raw, `${name} workflow input is required`);
  const url = new URL(raw);
  assert.equal(url.protocol, "https:", `${name} must use HTTPS`);
  assert.equal(url.username, "", `${name} must not contain credentials`);
  assert.equal(url.password, "", `${name} must not contain credentials`);
  assert.equal(url.search, "", `${name} must not contain a query string`);
  assert.equal(url.hash, "", `${name} must not contain a fragment`);
  return url;
}

test("dashboard origin passes live CORS preflight and backend rejects an invalid bearer token", async () => {
  const dashboardUrl = requiredHttpsUrl("DASHBOARD_URL");
  const backendUrl = requiredHttpsUrl("BACKEND_URL");
  assert.notEqual(dashboardUrl.origin, backendUrl.origin,
    "This workflow is specifically for cross-origin browser integration");

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
  const pageErrors = [];
  const preflightResponses = [];
  const apiResponses = [];
  page.on("pageerror", error => pageErrors.push(error.message));
  page.on("response", response => {
    if (!response.url().startsWith(backendUrl.origin + "/api/v1/research/phase-readiness")) return;
    if (response.request().method() === "OPTIONS") preflightResponses.push(response);
    if (response.request().method() === "GET") apiResponses.push(response);
  });

  try {
    const response = await page.goto(dashboardUrl.href, { waitUntil: "domcontentloaded", timeout: 45000 });
    assert.ok(response && response.ok(), `Dashboard navigation failed: HTTP ${response?.status()}`);

    const probe = await page.evaluate(async backend => {
      const response = await fetch(backend + "/api/v1/research/phase-readiness", {
        method: "GET",
        headers: {Authorization: "Bearer invalid-live-qa-probe"},
        credentials: "omit",
        cache: "no-store"
      });
      const payload = await response.json().catch(() => null);
      return {
        status: response.status,
        responseType: response.type,
        payloadIsObject: Boolean(payload && typeof payload === "object" && !Array.isArray(payload))
      };
    }, backendUrl.origin);

    assert.equal(probe.status, 401,
      "Backend must reject the deliberately invalid Bearer token with HTTP 401");
    assert.equal(probe.responseType, "cors",
      "The browser must receive a readable cross-origin CORS response");
    assert.ok(apiResponses.length > 0,
      "Playwright did not observe the cross-origin API response");
    const apiResponse = apiResponses[apiResponses.length - 1];
    const apiHeaders = await apiResponse.allHeaders();
    assert.equal(apiHeaders["access-control-allow-origin"], dashboardUrl.origin,
      "The actual API response must allow the exact dashboard origin");
    assert.equal(probe.payloadIsObject, true,
      "Unauthorized response must retain the JSON error envelope");
    assert.ok(preflightResponses.length > 0,
      "Browser did not issue an OPTIONS preflight for the Authorization header");

    const preflight = preflightResponses[preflightResponses.length - 1];
    const preflightHeaders = await preflight.allHeaders();
    assert.equal(preflight.status(), 200, "Authorization preflight did not return HTTP 200");
    assert.equal(preflightHeaders["access-control-allow-origin"], dashboardUrl.origin,
      "Preflight did not allow the exact dashboard origin");
    assert.match(preflightHeaders["access-control-allow-methods"] || "", /GET/,
      "Preflight did not allow GET");
    assert.match(preflightHeaders["access-control-allow-headers"] || "", /authorization/i,
      "Preflight did not allow the Authorization header");
    assert.equal(preflightHeaders["access-control-allow-credentials"], undefined,
      "Cookie credentials must remain disabled");
    assert.deepEqual(pageErrors, [], "Browser page errors were recorded");

    console.log(JSON.stringify({
      dashboardOrigin: dashboardUrl.origin,
      backendOrigin: backendUrl.origin,
      viewport: "390x844",
      invalidBearerProbe: {status: probe.status, responseType: probe.responseType, payloadIsObject: probe.payloadIsObject},
      actualResponseAllowedOrigin: apiHeaders["access-control-allow-origin"],
      preflight: {status: preflight.status(), allowedOrigin: preflightHeaders["access-control-allow-origin"]},
      pageErrors,
      authenticatedPositiveCheck: "not run; requires a separately scoped QA credential"
    }, null, 2));
  } finally {
    await browser.close();
  }
});
