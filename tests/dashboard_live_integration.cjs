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

test("Cloudflare-hosted dashboard reaches the supplied live backend health endpoint", async () => {
  const dashboardUrl = requiredHttpsUrl("DASHBOARD_URL");
  const backendUrl = requiredHttpsUrl("BACKEND_URL");
  const apiToken = process.env.DASHBOARD_QA_BEARER_TOKEN;
  assert.ok(apiToken && apiToken.length >= 32,
    "DASHBOARD_QA_BEARER_TOKEN must be configured as a masked repository Actions secret");
  assert.notEqual(dashboardUrl.origin, backendUrl.origin,
    "This workflow is specifically for cross-origin browser integration");

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
  const pageErrors = [];
  const preflightResponses = [];
  page.on("pageerror", error => pageErrors.push(error.message));
  page.on("response", response => {
    if (response.request().method() === "OPTIONS" &&
        response.url().startsWith(backendUrl.origin + "/api/v1/research/phase-readiness")) {
      preflightResponses.push(response);
    }
  });

  try {
    const response = await page.goto(dashboardUrl.href, { waitUntil: "domcontentloaded", timeout: 45000 });
    assert.ok(response && response.ok(), `Dashboard navigation failed: HTTP ${response?.status()}`);

    await page.locator("#backend-url").fill(backendUrl.origin);
    await page.locator("#backend-token").fill(apiToken);
    await page.locator("#test-connection").click();

    await page.waitForFunction(() => {
      const status = document.querySelector("#settings-status")?.textContent || "";
      return status.includes("responded successfully") || status.includes("Failed") ||
        status.includes("failed") || status.includes("Unavailable") || status.includes("Network connection");
    }, undefined, { timeout: 30000 });

    const settingsStatus = (await page.locator("#settings-status").innerText()).trim();
    const healthStatus = (await page.locator("#health-status").innerText()).trim();
    const connectionStatus = (await page.locator("#connection-label").innerText()).trim();

    assert.match(settingsStatus, /Backend health endpoint responded successfully\./,
      `Cross-origin connection did not succeed. Settings: ${settingsStatus}; health: ${healthStatus}; connection: ${connectionStatus}`);
    assert.match(healthStatus, /ok|healthy/i, "Live health response did not report a healthy status");

    const protectedApi = await page.evaluate(async ({backend, token}) => {
      const endpoint = backend + "/api/v1/research/phase-readiness";
      const unauthenticated = await fetch(endpoint, {method: "GET", credentials: "omit", cache: "no-store"});
      const unauthenticatedStatus = unauthenticated.status;
      const authenticated = await fetch(endpoint, {
        method: "GET",
        headers: {Authorization: "Bearer " + token},
        credentials: "omit",
        cache: "no-store"
      });
      const payload = await authenticated.json();
      return {
        unauthenticatedStatus,
        authenticatedStatus: authenticated.status,
        payloadIsObject: Boolean(payload && typeof payload === "object" && !Array.isArray(payload))
      };
    }, {backend: backendUrl.origin, token: apiToken});

    assert.equal(protectedApi.unauthenticatedStatus, 401,
      "Protected API unexpectedly accepted a request without a Bearer token");
    assert.equal(protectedApi.authenticatedStatus, 200,
      "Protected API did not accept the configured QA Bearer token");
    assert.equal(protectedApi.payloadIsObject, true,
      "Protected API did not return a JSON object");
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
      healthStatus,
      connectionStatus,
      protectedApi,
      preflight: {status: preflight.status(), allowedOrigin: preflightHeaders["access-control-allow-origin"]},
      pageErrors
    }, null, 2));
  } finally {
    await browser.close();
  }
});
