"use strict";

const {test, before, after} = require("node:test");
const assert = require("node:assert/strict");
const http = require("node:http");
const fs = require("node:fs");
const path = require("node:path");
const {chromium} = require("playwright");

const root = path.resolve(__dirname, "..", "dashboard");
let server;
let origin;
let browser;

before(async () => {
  server = http.createServer((req, res) => {
    const pathname = decodeURIComponent(new URL(req.url, "http://127.0.0.1").pathname);
    const file = path.resolve(root, "." + pathname);
    if (file !== root && !file.startsWith(root + path.sep)) {
      res.writeHead(403).end("Forbidden");
      return;
    }
    let target = file;
    if (pathname === "/") target = path.join(root, "index.html");
    fs.readFile(target, (error, body) => {
      if (error) {
        res.writeHead(404).end("Not found");
        return;
      }
      const type = target.endsWith(".html") ? "text/html; charset=utf-8"
        : target.endsWith(".css") ? "text/css; charset=utf-8"
        : "text/javascript; charset=utf-8";
      res.writeHead(200, {"content-type": type, "cache-control": "no-store"});
      res.end(body);
    });
  });
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  origin = "http://127.0.0.1:" + server.address().port;
  browser = await chromium.launch({headless: true});
});

after(async () => {
  if (browser) await browser.close();
  if (server) await new Promise(resolve => server.close(resolve));
});

async function newPage(width, height = 900) {
  const context = await browser.newContext({viewport: {width, height}});
  const page = await context.newPage();
  const pageErrors = [];
  page.on("pageerror", error => pageErrors.push(error.message));
  await page.goto(origin, {waitUntil: "networkidle"});
  return {context, page, pageErrors};
}

test("responsive layout has no horizontal overflow at supported viewport widths", async () => {
  for (const width of [360, 390, 480, 760, 768, 1100, 1280]) {
    const {context, page, pageErrors} = await newPage(width);
    const metrics = await page.evaluate(() => ({
      viewport: document.documentElement.clientWidth,
      document: document.documentElement.scrollWidth,
      body: document.body.scrollWidth
    }));
    assert.ok(metrics.document <= metrics.viewport + 1,
      width + "px document overflow: " + JSON.stringify(metrics));
    assert.ok(metrics.body <= metrics.viewport + 1,
      width + "px body overflow: " + JSON.stringify(metrics));
    assert.deepEqual(pageErrors, [], width + "px runtime errors");
    await context.close();
  }
});

test("mobile sidebar opens, traps keyboard focus, closes with Escape and restores focus", async () => {
  const {context, page} = await newPage(390);
  const menu = page.locator("#mobile-menu");
  const sidebar = page.locator("#sidebar");
  assert.equal(await sidebar.evaluate(el => el.inert), true,
    "closed mobile navigation must be removed from keyboard interaction");
  await menu.click();
  assert.equal(await menu.getAttribute("aria-expanded"), "true");
  assert.equal(await sidebar.evaluate(el => el.inert), false);

  const focusableCount = await sidebar.locator('a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])').count();
  assert.ok(focusableCount > 1, "sidebar should expose keyboard navigation targets");

  const first = sidebar.locator('a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])').first();
  const last = sidebar.locator('a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])').last();
  await first.evaluate(el => el.focus());
  await page.keyboard.press("Shift+Tab");
  assert.equal(await page.evaluate(() => document.activeElement?.getAttribute("data-page")), await last.getAttribute("data-page"));
  await page.keyboard.press("Tab");
  assert.equal(await page.evaluate(() => document.activeElement?.getAttribute("data-page")), await first.getAttribute("data-page"));

  await page.keyboard.press("Escape");
  assert.equal(await menu.getAttribute("aria-expanded"), "false");
  assert.equal(await sidebar.evaluate(el => el.inert), true);
  assert.equal(await page.evaluate(() => document.activeElement.id), "mobile-menu");
  await context.close();
});

test("backend health success updates connection status without page errors", async () => {
  const {context, page, pageErrors} = await newPage(1280);
  await page.locator('.nav-link[data-page="settings"]').click();
  await page.route("https://backend.test/health", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    headers: {"access-control-allow-origin": "*"},
    body: JSON.stringify({status: "ok"})
  }));
  await page.locator("#backend-url").fill("https://backend.test");
  await page.locator("#test-connection").click();
  await page.getByText("Backend health endpoint responded successfully.").waitFor();
  assert.match(await page.locator("#health-status").innerText(), /ok/i);
  assert.deepEqual(pageErrors, []);
  await context.close();
});

test("API HTTP 503 and malformed JSON failures are visible and do not crash the dashboard", async () => {
  const {context, page, pageErrors} = await newPage(1280);
  await page.locator('.nav-link[data-page="settings"]').click();
  await page.route("https://backend.test/health", route => route.fulfill({
    status: 503,
    contentType: "application/json",
    headers: {"access-control-allow-origin": "*"},
    body: JSON.stringify({detail: "service unavailable"})
  }));
  await page.locator("#backend-url").fill("https://backend.test");
  await page.locator("#test-connection").click();
  await page.locator(".toast.error").filter({hasText: "service unavailable"}).waitFor();
  assert.match(await page.locator("#health-status").innerText(), /unavailable/i);

  await page.unrouteAll();
  await page.route("https://backend.test/health", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    headers: {"access-control-allow-origin": "*"},
    body: "<html>not json</html>"
  }));
  await page.locator("#test-connection").click();
  await page.locator(".toast.error").filter({hasText: "non-JSON response"}).waitFor();
  assert.deepEqual(pageErrors, []);
  await context.close();
});

test("network failure, empty JSON success and invalid health shape are handled safely", async () => {
  const {context, page, pageErrors} = await newPage(1280);
  await page.locator('.nav-link[data-page="settings"]').click();
  await page.locator("#backend-url").fill("https://backend.test");

  await page.route("https://backend.test/health", route => route.abort("failed"));
  await page.locator("#test-connection").click();
  await page.locator(".toast.error").filter({hasText: "Network connection failed"}).waitFor();
  assert.match(await page.locator("#health-status").innerText(), /unavailable/i);

  await page.unrouteAll();
  await page.route("https://backend.test/health", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    headers: {"access-control-allow-origin": "*"},
    body: ""
  }));
  await page.locator("#test-connection").click();
  await page.locator(".toast.error").filter({hasText: "empty JSON response"}).waitFor();

  await page.unrouteAll();
  await page.route("https://backend.test/health", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    headers: {"access-control-allow-origin": "*"},
    body: JSON.stringify(["unexpected", "array"])
  }));
  await page.locator("#test-connection").click();
  await page.locator(".toast.error").filter({hasText: "invalid response shape"}).waitFor();
  assert.match(await page.locator("#health-status").innerText(), /unavailable/i);
  assert.deepEqual(pageErrors, []);
  await context.close();
});

test("document landmarks and reduced-motion preference are honored", async () => {
  const {context, page, pageErrors} = await newPage(1280);
  assert.equal(await page.locator("main").count(), 1);
  assert.equal(await page.locator("header").count(), 1);
  assert.equal(await page.locator('nav[aria-label="Primary navigation"]').count(), 1);
  await page.emulateMedia({reducedMotion: "reduce"});
  const transitionDuration = await page.locator("#sidebar").evaluate(el => getComputedStyle(el).transitionDuration);
  assert.match(transitionDuration, /^(0s|0ms)$/);
  assert.deepEqual(pageErrors, []);
  await context.close();
});

test("API timeout is reported without an uncaught browser exception", async () => {
  const {context, page, pageErrors} = await newPage(1280);
  await page.addInitScript(() => {
    const originalSetTimeout = window.setTimeout.bind(window);
    window.setTimeout = (callback, delay, ...args) =>
      originalSetTimeout(callback, delay === 20000 ? 40 : delay, ...args);
  });
  await page.reload({waitUntil: "networkidle"});
  await page.locator('.nav-link[data-page="settings"]').click();
  await page.route("https://backend.test/health", route =>
    new Promise(resolve => setTimeout(() => resolve(route.fulfill({
      status: 200,
      contentType: "application/json",
      headers: {"access-control-allow-origin": "*"},
      body: JSON.stringify({status: "late"})
    })), 250))
  );
  await page.locator("#backend-url").fill("https://backend.test");
  await page.locator("#test-connection").click();
  await page.locator(".toast.error").filter({hasText: "Request timed out"}).waitFor();
  assert.match(await page.locator("#health-status").innerText(), /unavailable/i);
  assert.deepEqual(pageErrors, []);
  await context.close();
});

test("changing market cancels an in-flight scan without an uncaught error", async () => {
  const {context, page, pageErrors} = await newPage(1280);
  await page.addInitScript(() => {
    const originalFetch = window.fetch.bind(window);
    window.__scanAbortObserved = false;
    window.fetch = (input, init = {}) => {
      const url = typeof input === "string" ? input : input.url;
      if (url.includes("/api/v1/markets/spot/scan") && init.signal) {
        if (init.signal.aborted) window.__scanAbortObserved = true;
        else init.signal.addEventListener("abort", () => {
          window.__scanAbortObserved = true;
        }, {once: true});
      }
      return originalFetch(input, init);
    };
  });
  await page.reload({waitUntil: "networkidle"});
  await page.locator('.nav-link[data-page="settings"]').click();
  await page.route("https://backend.test/health", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    headers: {"access-control-allow-origin": "*"},
    body: JSON.stringify({status: "ok"})
  }));
  await page.locator("#backend-url").fill("https://backend.test");
  await page.locator("#test-connection").click();
  await page.getByText("Backend health endpoint responded successfully.").waitFor();
  await page.locator('.nav-link[data-page="overview"]').click();

  let scanStarted, routeSettled;
  const started = new Promise(resolve => { scanStarted = resolve; });
  const routeFinished = new Promise(resolve => { routeSettled = resolve; });
  await page.route("https://backend.test/api/v1/markets/spot/scan", async route => {
    scanStarted();
    await new Promise(resolve => setTimeout(resolve, 500));
    try {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        headers: {"access-control-allow-origin": "*"},
        body: JSON.stringify({symbols: []})
      });
    } catch { /* The client intentionally aborted this mocked request. */ }
    finally { routeSettled(); }
  });
  await page.locator("#run-market-scan").click();
  await started;
  await page.locator("#global-market").selectOption("USD_M");
  await page.waitForFunction(() => window.__scanAbortObserved === true);
  await routeFinished;
  assert.match(await page.locator("#scan-state").innerText(), /Market selection changed/i);
  assert.deepEqual(pageErrors, []);
  await context.close();
});