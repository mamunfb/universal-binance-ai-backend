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
  assert.notEqual(dashboardUrl.origin, backendUrl.origin,
    "This workflow is specifically for cross-origin browser integration");

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
  const pageErrors = [];
  page.on("pageerror", error => pageErrors.push(error.message));

  try {
    const response = await page.goto(dashboardUrl.href, { waitUntil: "domcontentloaded", timeout: 45000 });
    assert.ok(response && response.ok(), `Dashboard navigation failed: HTTP ${response?.status()}`);

    await page.locator("#backend-url").fill(backendUrl.origin);
    await page.locator("#backend-token").fill("");
    await page.locator("#test-connection").click();

    await page.waitForFunction(() => {
      const status = document.querySelector("#settings-status")?.textContent || "";
      return status.includes("responded successfully") || status.includes("Failed") ||
        status.includes("failed") || status.includes("Unavailable") || status.includes("Network connection");
    }, { timeout: 30000 });

    const settingsStatus = (await page.locator("#settings-status").innerText()).trim();
    const healthStatus = (await page.locator("#health-status").innerText()).trim();
    const connectionStatus = (await page.locator("#connection-label").innerText()).trim();

    assert.match(settingsStatus, /Backend health endpoint responded successfully\./,
      `Cross-origin connection did not succeed. Settings: ${settingsStatus}; health: ${healthStatus}; connection: ${connectionStatus}`);
    assert.match(healthStatus, /ok|healthy/i, "Live health response did not report a healthy status");
    assert.deepEqual(pageErrors, [], "Browser page errors were recorded");

    console.log(JSON.stringify({
      dashboardOrigin: dashboardUrl.origin,
      backendOrigin: backendUrl.origin,
      viewport: "390x844",
      healthStatus,
      connectionStatus,
      pageErrors
    }, null, 2));
  } finally {
    await browser.close();
  }
});
