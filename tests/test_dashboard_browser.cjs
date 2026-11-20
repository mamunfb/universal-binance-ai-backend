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
  for (const width of [320, 344, 360, 390, 480, 760, 768, 900, 1100, 1280]) {
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

test("mobile keyboard Tab navigation exposes a visible focus indicator on the menu button", async () => {
  const {context, page, pageErrors} = await newPage(390, 844);
  await page.keyboard.press("Tab");

  const focus = await page.evaluate(() => {
    const element = document.activeElement;
    const style = element ? getComputedStyle(element) : null;
    return {
      tag: element?.tagName,
      className: element?.className,
      outlineStyle: style?.outlineStyle,
      outlineWidth: style?.outlineWidth,
      outlineColor: style?.outlineColor
    };
  });

  assert.equal(focus.tag, "BUTTON", "the first Tab stop at a mobile viewport should be the mobile navigation control");
  assert.equal(await page.evaluate(() => document.activeElement.id), "mobile-menu");
  assert.match(String(focus.className), /icon-btn/);
  assert.equal(focus.outlineStyle, "solid", "keyboard focus must have a visible outline");
  assert.equal(focus.outlineWidth, "2px", "keyboard focus outline must be at least 2 CSS pixels");
  assert.notEqual(focus.outlineColor, "rgba(0, 0, 0, 0)",
    "keyboard focus outline must not be transparent");
  assert.deepEqual(pageErrors, []);
  await context.close();
});

test("mobile sidebar opens, traps keyboard focus, closes with Escape and restores focus", async () => {
  const {context, page} = await newPage(390);
  const menu = page.locator("#mobile-menu");
  const sidebar = page.locator("#sidebar");
  assert.equal(await sidebar.evaluate(el => el.inert), true,
    "closed mobile navigation must be removed from keyboard interaction");
  assert.equal(await menu.getAttribute("aria-label"), "Open navigation");
  await menu.click();
  assert.equal(await menu.getAttribute("aria-expanded"), "true");
  assert.equal(await menu.getAttribute("aria-label"), "Close navigation");
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
  assert.equal(await menu.getAttribute("aria-label"), "Open navigation");
  assert.equal(await sidebar.evaluate(el => el.inert), true);
  assert.equal(await page.evaluate(() => document.activeElement.id), "mobile-menu");
  await context.close();
});

test("backend root URL validation accepts root origins and normalizes multiple trailing slashes", async () => {
  for (const input of ["https://backend.test", "https://backend.test/", "https://backend.test////"]) {
    const {context, page, pageErrors} = await newPage(1280);
    await page.locator('.nav-link[data-page="settings"]').click();
    await page.route("https://backend.test/health", route => route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({status: "ok"})
    }));
    await page.locator("#backend-url").fill(input);
    await page.locator("#test-connection").click();
    await page.getByText("Backend health endpoint responded successfully.").waitFor();
    assert.equal(await page.locator("#connection-label").innerText(), "Backend reachable", input);
    assert.deepEqual(pageErrors, [], input + " browser errors");
    await context.close();
  }
});

test("backend URL API paths are rejected without a request or changing the prior connection state", async () => {
  for (const invalidInput of ["https://backend.test/api", "https://backend.test/api/"]) {
    const {context, page, pageErrors} = await newPage(1280);
    await page.locator('.nav-link[data-page="settings"]').click();
    await page.route("https://backend.test/health", route => route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({status: "ok"})
    }));
    const backendRequests = [];
    page.on("request", request => {
      if (new URL(request.url()).origin === "https://backend.test") backendRequests.push(request.url());
    });
    await page.locator("#backend-url").fill("https://backend.test");
    await page.locator("#test-connection").click();
    await page.getByText("Backend health endpoint responded successfully.").waitFor();
    assert.equal(await page.locator("#connection-label").innerText(), "Backend reachable");

    backendRequests.length = 0;
    const previousHealthStatus = await page.locator("#health-status").innerText();
    await page.locator("#backend-url").fill(invalidInput);
    await page.locator("#test-connection").click();
    await page.locator(".toast.error").filter({hasText: "root origin without an API path"}).waitFor();
    assert.deepEqual(backendRequests, [], invalidInput + " must not issue a backend request");
    assert.equal(await page.locator("#connection-label").innerText(), "Backend reachable",
      invalidInput + " must preserve the prior connection state");
    assert.equal(await page.locator("#health-status").innerText(), previousHealthStatus,
      invalidInput + " must preserve the previous health status");
    assert.deepEqual(pageErrors, []);
    await context.close();
  }
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
  assert.equal(await page.getByRole("main").count(), 1);
  assert.equal(await page.locator("header.topbar").count(), 1);
  const navigation = page.getByRole("navigation", {name: "Primary navigation"});
  assert.equal(await navigation.count(), 1);
  assert.equal(await navigation.locator(".nav-link.active").getAttribute("aria-current"), "page");
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

test("1000-row scanner response stays paginated, searchable and keyboard-sortable on mobile", async () => {
  const {context, page, pageErrors} = await newPage(390, 844);
  await page.route("https://backend.test/health", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    headers: {"access-control-allow-origin": "*"},
    body: JSON.stringify({status: "ok"})
  }));
  await page.locator("#mobile-menu").click();
  await page.locator('.nav-link[data-page="settings"]').click();
  await page.locator("#backend-url").fill("https://backend.test");
  await page.locator("#test-connection").click();
  await page.getByText("Backend health endpoint responded successfully.").waitFor();

  const symbols = Array.from({length: 1000}, (_, index) => ({
    symbol: "ASSET" + String(index).padStart(4, "0") + "USDT",
    base_asset: "ASSET" + String(index).padStart(4, "0"),
    quote_asset: "USDT",
    last_price: index + 0.25,
    quote_volume_24h: index * 1000,
    status: "TRADING"
  }));
  await page.route("https://backend.test/api/v1/markets/spot/scan**", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    headers: {"access-control-allow-origin": "*"},
    body: JSON.stringify({symbols, eligible_count: 1000, scanned_count: 1000, failed_count: 0})
  }));

  await page.locator("#mobile-menu").click();
  await page.locator('.nav-link[data-page="spot-scanner"]').click();
  await page.locator("#scan-spot").click();
  await page.locator("#spot-rows tr").nth(99).waitFor();
  assert.equal(await page.locator("#spot-rows tr").count(), 100,
    "the DOM must contain only one 100-row page, not all 1000 rows");
  const pager = page.locator("#page-spot-scanner .table-pager");
  assert.match(await pager.innerText(), /1,000 matching \/ 1,000 returned/);
  assert.match(await pager.innerText(), /page 1\/10/);

  const symbolHeader = page.locator("#page-spot-scanner thead th").first();
  await symbolHeader.focus();
  await page.keyboard.press("Enter");
  assert.equal(await symbolHeader.getAttribute("aria-sort"), "descending");
  assert.equal(await page.locator("#spot-rows tr").first().locator("td").first().innerText(), "ASSET0999USDT");
  await page.keyboard.press("Space");
  assert.equal(await symbolHeader.getAttribute("aria-sort"), "ascending");
  assert.equal(await page.locator("#spot-rows tr").first().locator("td").first().innerText(), "ASSET0000USDT");

  await page.locator("#spot-search").fill("ASSET0999");
  await page.waitForFunction(() => document.querySelector("#page-spot-scanner .table-pager")?.textContent.includes("1 matching / 1,000 returned"));
  assert.equal(await page.locator("#spot-rows tr").count(), 1);
  assert.match(await pager.innerText(), /1 matching \/ 1,000 returned/);

  await page.locator("#spot-search").fill("");
  await page.waitForFunction(() => document.querySelector("#page-spot-scanner .table-pager")?.textContent.includes("page 1/10"));
  const nextPage = page.locator("#page-spot-scanner").getByRole("button", {name: "Next scanner page"});
  await nextPage.click();
  assert.match(await pager.innerText(), /page 2\/10/);
  assert.equal(await page.locator("#spot-rows tr").count(), 100);
  assert.equal(await page.evaluate(() => document.activeElement?.getAttribute("aria-label")), "Next scanner page",
    "keyboard focus should remain on Next after pagination rerenders");
  await page.keyboard.press("Enter");
  assert.match(await pager.innerText(), /page 3\/10/);
  assert.equal(await page.evaluate(() => document.activeElement?.getAttribute("aria-label")), "Next scanner page");
  await page.locator("#page-spot-scanner").getByRole("button", {name: "Previous scanner page"}).focus();
  await page.keyboard.press("Space");
  assert.match(await pager.innerText(), /page 2\/10/);
  assert.equal(await page.evaluate(() => document.activeElement?.getAttribute("aria-label")), "Previous scanner page");

  const widths = await page.evaluate(() => ({
    viewport: document.documentElement.clientWidth,
    document: document.documentElement.scrollWidth,
    body: document.body.scrollWidth
  }));
  assert.ok(widths.document <= widths.viewport + 1, "mobile document overflow: " + JSON.stringify(widths));
  assert.ok(widths.body <= widths.viewport + 1, "mobile body overflow: " + JSON.stringify(widths));
  assert.deepEqual(pageErrors, []);
  await context.close();
});


test("visible dashboard UI passes WCAG 2.1 A/AA automated accessibility checks", async () => {
  const {context, page, pageErrors} = await newPage(1280);
  await page.addScriptTag({path: require.resolve("axe-core")});
  const results = await page.evaluate(async () => window.axe.run(document, {
    runOnly: {type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]}
  }));
  const violations = results.violations.map(item => ({
    id: item.id,
    impact: item.impact,
    description: item.description,
    nodes: item.nodes.map(node => ({target: node.target, summary: node.failureSummary}))
  }));
  assert.deepEqual(violations, [], "axe-core WCAG violations: " + JSON.stringify(violations));
  assert.deepEqual(pageErrors, []);
  await context.close();
});

test("API authentication, authorization, rate-limit and server errors remain visible and text-only", async () => {
  const {context, page, pageErrors} = await newPage(1280);
  await page.locator('.nav-link[data-page="settings"]').click();
  await page.locator("#backend-url").fill("https://backend.test");
  const cases = [
    {status: 401, detail: "authentication required"},
    {status: 403, detail: "permission denied"},
    {status: 429, detail: "rate limit exceeded"},
    {status: 500, detail: "internal server error"},
    {status: 403, detail: "access denied <img src=x onerror=alert(1)>"}
  ];
  let activeCase = cases[0];
  await page.route("https://backend.test/health", route => route.fulfill({
    status: activeCase.status,
    contentType: "application/json",
    headers: {"access-control-allow-origin": "*"},
    body: JSON.stringify({detail: activeCase.detail})
  }));

  for (const item of cases) {
    activeCase = item;
    await page.locator("#test-connection").click();
    const toast = page.locator(".toast.error").filter({hasText: item.detail});
    await toast.waitFor();
    assert.match(await page.locator("#health-status").innerText(), /unavailable/i);
    assert.equal(await toast.locator("img").count(), 0,
      "backend error details must be rendered as text, not executable markup");
  }
  assert.deepEqual(pageErrors, []);
  await context.close();
});

test("mobile navigation remains inert and focus-safe across desktop/mobile viewport changes", async () => {
  const {context, page, pageErrors} = await newPage(390, 844);
  const menu = page.locator("#mobile-menu");
  const sidebar = page.locator("#sidebar");
  await menu.click();
  assert.equal(await sidebar.evaluate(el => el.inert), false);

  const firstLink = sidebar.locator(".nav-link").first();
  await firstLink.focus();
  await page.setViewportSize({width: 1024, height: 900});
  await page.waitForFunction(() => !document.querySelector("#sidebar").classList.contains("open"));
  assert.equal(await sidebar.evaluate(el => el.inert), false);
  assert.equal(await menu.getAttribute("aria-expanded"), "false");

  await page.setViewportSize({width: 390, height: 844});
  await page.waitForFunction(() => document.querySelector("#sidebar").inert === true);
  assert.equal(await page.evaluate(() => document.activeElement.id), "mobile-menu",
    "focus must leave the sidebar before it becomes inert on mobile");
  assert.equal(await menu.getAttribute("aria-expanded"), "false");
  assert.deepEqual(pageErrors, []);
  await context.close();
});

test("mobile dashboard accessibility is checked with navigation both closed and open", async () => {
  const {context, page, pageErrors} = await newPage(390, 844);
  await page.addScriptTag({path: require.resolve("axe-core")});
  const menu = page.locator("#mobile-menu");
  const sidebar = page.locator("#sidebar");

  const scan = async state => {
    const results = await page.evaluate(async () => window.axe.run(document, {
      runOnly: {type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]}
    }));
    const violations = results.violations.map(item => ({
      id: item.id,
      impact: item.impact,
      nodes: item.nodes.map(node => node.target)
    }));
    assert.deepEqual(violations, [], "mobile " + state + " accessibility violations: " + JSON.stringify(violations));
  };

  assert.equal(await sidebar.evaluate(el => el.inert), true);
  await scan("closed navigation");
  await menu.click();
  assert.equal(await sidebar.evaluate(el => el.inert), false);
  await scan("open navigation");
  await page.keyboard.press("Escape");
  assert.equal(await sidebar.evaluate(el => el.inert), true);
  assert.deepEqual(pageErrors, []);
  await context.close();
});

test("backend requests never send browser cookies and use no-store caching", async () => {
  const {context, page, pageErrors} = await newPage(1280);
  await page.addInitScript(() => {
    const originalFetch = window.fetch.bind(window);
    window.__backendFetchOptions = [];
    window.fetch = (input, init = {}) => {
      const url = typeof input === "string" ? input : input.url;
      if (url.startsWith("https://backend.test/")) {
        window.__backendFetchOptions.push({
          cache: init.cache,
          credentials: init.credentials
        });
      }
      return originalFetch(input, init);
    };
  });
  await page.reload({waitUntil: "networkidle"});
  await page.locator('.nav-link[data-page="settings"]').click();
  await page.locator("#backend-url").fill("https://backend.test");
  await context.addCookies([{
    name: "dashboard-session",
    value: "must-not-leave-browser",
    url: "https://backend.test"
  }]);

  let observedCookieHeader = null;
  await page.route("https://backend.test/health", async route => {
    observedCookieHeader = route.request().headers()["cookie"] ?? null;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      headers: {"access-control-allow-origin": "*"},
      body: JSON.stringify({status: "ok"})
    });
  });
  await page.locator("#test-connection").click();
  await page.getByText("Backend health endpoint responded successfully.").waitFor();
  const options = await page.evaluate(() => window.__backendFetchOptions.at(-1));
  assert.equal(observedCookieHeader, null, "browser cookies must not accompany API requests");
  assert.equal(options?.credentials, "omit");
  assert.equal(options?.cache, "no-store");
  assert.deepEqual(pageErrors, []);
  await context.close();
});

test("clearing backend credentials cancels an in-flight health check without stale status", async () => {
  const {context, page, pageErrors} = await newPage(1280);
  await page.addInitScript(() => {
    window.__healthAbortObserved = false;
    const originalFetch = window.fetch.bind(window);
    window.fetch = (input, init = {}) => {
      const url = typeof input === "string" ? input : input.url;
      if (url === "https://backend.test/health" && init.signal) {
        init.signal.addEventListener("abort", () => {
          window.__healthAbortObserved = true;
        }, {once: true});
      }
      return originalFetch(input, init);
    };
  });
  await page.reload({waitUntil: "networkidle"});
  await page.locator('.nav-link[data-page="settings"]').click();
  await page.locator("#backend-url").fill("https://backend.test");

  let requestStarted;
  let routeSettled;
  const started = new Promise(resolve => { requestStarted = resolve; });
  const settled = new Promise(resolve => { routeSettled = resolve; });
  await page.route("https://backend.test/health", async route => {
    requestStarted();
    await new Promise(resolve => setTimeout(resolve, 350));
    try {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        headers: {"access-control-allow-origin": "*"},
        body: JSON.stringify({status: "stale late response"})
      });
    } catch { /* Credential clearing intentionally aborts this request. */ }
    finally { routeSettled(); }
  });

  await page.locator("#test-connection").click();
  await started;
  await page.locator("#clear-credentials").click();
  await page.waitForFunction(() => window.__healthAbortObserved === true);
  await settled;

  assert.equal(await page.locator("#health-status").innerText(),
    "Not checked · backend credentials cleared");
  assert.equal(await page.locator("#connection-label").innerText(), "Not connected");
  assert.equal(await page.locator("#settings-status").innerText(),
    "Credentials cleared from page memory.");
  assert.deepEqual(pageErrors, []);
  await context.close();
});

test("asynchronous dashboard status outputs retain polite atomic live-region semantics", async () => {
  const {context, page, pageErrors} = await newPage(1280);
  const statusIds = [
    "connection-label",
    "scan-state",
    "health-status",
    "chart-state",
    "technical-summary",
    "settings-status",
    "quality-state"
  ];
  for (const id of statusIds) {
    const status = page.locator("#" + id);
    assert.equal(await status.getAttribute("role"), "status", id + " must expose status semantics");
    assert.equal(await status.getAttribute("aria-live"), "polite", id + " must announce updates politely");
    assert.equal(await status.getAttribute("aria-atomic"), "true", id + " must announce the complete status");
  }
  assert.equal(await page.locator("#toast-region").getAttribute("aria-live"), "polite",
    "transient toast feedback must be exposed through a polite live region");
  assert.deepEqual(pageErrors, []);
  await context.close();
});

test("a newer market scan wins when an older scan response arrives late", async () => {
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

  let oldScanStarted;
  let oldScanSettled;
  const started = new Promise(resolve => { oldScanStarted = resolve; });
  const settled = new Promise(resolve => { oldScanSettled = resolve; });
  await page.route("https://backend.test/api/v1/markets/spot/scan", async route => {
    oldScanStarted();
    await new Promise(resolve => setTimeout(resolve, 400));
    try {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        headers: {"access-control-allow-origin": "*"},
        body: JSON.stringify({symbols: [{
          symbol: "STALESPOTUSDT", base_asset: "STALESPOT", quote_asset: "USDT",
          last_price: 1, quote_volume_24h: 10, status: "TRADING"
        }]})
      });
    } catch { /* The newer market selection intentionally supersedes this request. */ }
    finally { oldScanSettled(); }
  });
  await page.route("https://backend.test/api/v1/markets/futures/usdm/scan", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    headers: {"access-control-allow-origin": "*"},
    body: JSON.stringify({symbols: [{
      symbol: "CURRENTUSDT", base_asset: "CURRENT", quote_asset: "USDT",
      last_price: 2, quote_volume_24h: 20, status: "TRADING"
    }]})
  }));

  await page.locator('.nav-link[data-page="overview"]').click();
  await page.locator("#run-market-scan").click();
  await started;
  await page.locator('.nav-link[data-page="usdm-scanner"]').click();
  await page.locator("#scan-usdm").click();
  await page.locator("#usdm-rows tr").first().getByText("CURRENTUSDT").waitFor();
  await settled;

  assert.equal(await page.locator("#usdm-rows tr").first().locator("td").first().innerText(), "CURRENTUSDT",
    "the late Spot response must not replace the latest USDⓈ-M results");
  assert.equal(await page.locator("#spot-rows").getByText("STALESPOTUSDT").count(), 0,
    "the superseded Spot response must not render stale market rows");
  assert.equal(await page.locator("#global-market").inputValue(), "USD_M");
  assert.equal(await page.locator("#scan-state").innerText(), "Response received");
  assert.deepEqual(pageErrors, []);
  await context.close();
});


test("a newer data-quality selection wins when an older report arrives late", async () => {
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

  let oldStarted;
  let oldSettled;
  const started = new Promise(resolve => { oldStarted = resolve; });
  const settled = new Promise(resolve => { oldSettled = resolve; });
  await page.route("https://backend.test/api/v1/quality/market-data/SPOT/BTCUSDT**", async route => {
    oldStarted();
    await new Promise(resolve => setTimeout(resolve, 400));
    try {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        headers: {"access-control-allow-origin": "*"},
        body: JSON.stringify({status: "stale-btc", symbol: "BTCUSDT"})
      });
    } catch { /* The changed quality selection intentionally aborts this request. */ }
    finally { oldSettled(); }
  });
  await page.route("https://backend.test/api/v1/quality/market-data/SPOT/ETHUSDT**", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    headers: {"access-control-allow-origin": "*"},
    body: JSON.stringify({status: "current-eth", symbol: "ETHUSDT"})
  }));

  await page.locator('.nav-link[data-page="reliability"]').click();
  await page.locator("#load-quality").click();
  await started;
  await page.locator("#quality-symbol").fill("ETHUSDT");
  await page.locator("#load-quality").click();
  await page.getByText('"current-eth"', {exact: false}).waitFor();
  await settled;

  assert.match(await page.locator("#quality-output").innerText(), /ETHUSDT/);
  assert.match(await page.locator("#quality-output").innerText(), /current-eth/);
  assert.equal(await page.locator("#quality-state").innerText(), "current-eth");
  assert.doesNotMatch(await page.locator("#quality-output").innerText(), /stale-btc/);
  assert.deepEqual(pageErrors, []);
  await context.close();
});

test("the latest research-readiness request wins when an older endpoint responds late", async () => {
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

  let oldStarted;
  let oldSettled;
  const started = new Promise(resolve => { oldStarted = resolve; });
  const settled = new Promise(resolve => { oldSettled = resolve; });
  await page.route("https://backend.test/api/v1/research/preflight", async route => {
    oldStarted();
    await new Promise(resolve => setTimeout(resolve, 400));
    try {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        headers: {"access-control-allow-origin": "*"},
        body: JSON.stringify({status: "stale-preflight", marker: "old"})
      });
    } catch { /* The phase-readiness request intentionally supersedes preflight. */ }
    finally { oldSettled(); }
  });
  await page.route("https://backend.test/api/v1/research/phase-readiness", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    headers: {"access-control-allow-origin": "*"},
    body: JSON.stringify({status: "current-readiness", marker: "new"})
  }));

  await page.locator('.nav-link[data-page="overview"]').click();
  await page.locator("#load-preflight").click();
  await started;
  await page.locator("#load-readiness").click();
  await page.getByText('"current-readiness"', {exact: false}).waitFor();
  await settled;

  assert.match(await page.locator("#readiness-output").innerText(), /current-readiness/);
  assert.match(await page.locator("#readiness-output").innerText(), /new/);
  assert.equal(await page.locator("#readiness-state").innerText(), "current-readiness");
  assert.doesNotMatch(await page.locator("#readiness-output").innerText(), /stale-preflight/);
  assert.deepEqual(pageErrors, []);
  await context.close();
});


test("visible pointer targets are inventoried against WCAG 2.2 24px minimum for manual spacing review", async () => {
  const reports = [];
  for (const width of [320, 360, 390, 480, 900]) {
    const {context, page, pageErrors} = await newPage(width, 844);
    const collect = async state => {
      const inventory = await page.evaluate(() => {
        const selector = 'button,input:not([type="hidden"]),select,textarea,a[href],[role="button"],[role="link"],[tabindex]:not([tabindex="-1"])';
        const elements = [...new Set(document.querySelectorAll(selector))];
        const visible = elements.filter(el => {
          const style = getComputedStyle(el);
          const sidebar = el.closest(".sidebar");
          const mobileSidebarClosed = sidebar &&
            window.matchMedia("(max-width: 900px)").matches &&
            !sidebar.classList.contains("open");
          if (!el.getClientRects().length || style.display === "none" ||
              style.visibility === "hidden" || Number(style.opacity) === 0 ||
              el.closest("[inert]") || mobileSidebarClosed) return false;
          const rect = el.getBoundingClientRect();
          return rect.width > 0 && rect.height > 0;
        });
        const candidates = visible.map(el => {
          const rect = el.getBoundingClientRect();
          return {
            tag: el.tagName.toLowerCase(),
            id: el.id || null,
            label: (el.getAttribute("aria-label") || el.innerText || el.getAttribute("title") || "").trim().slice(0, 80),
            width: Math.round(rect.width * 100) / 100,
            height: Math.round(rect.height * 100) / 100
          };
        }).filter(item => item.width < 24 || item.height < 24);
        return {visibleInteractiveCount: visible.length, candidates};
      });
      assert.ok(inventory.visibleInteractiveCount > 0,
        width + "px " + state + " should inventory visible interactive controls");
      assert.ok(!inventory.candidates.some(item => item.id === "banner-settings"),
        width + "px " + state + " Configure connection target is below 24px: " +
          JSON.stringify(inventory.candidates.find(item => item.id === "banner-settings")));
      reports.push({viewport: width, state, visibleInteractiveCount: inventory.visibleInteractiveCount,
        undersizedCandidatesForSpacingReview: inventory.candidates});
    };
    await collect("navigation closed");
    await page.locator("#mobile-menu").click();
    await collect("navigation open");
    assert.deepEqual(pageErrors, [], width + "px runtime errors");
    await context.close();
  }
  console.log("WCAG 2.2 target-size candidate inventory (manual spacing/exception review required):",
    JSON.stringify(reports));
});

test("dedicated WCAG text-contrast scan reports desktop and mobile navigation states", async () => {
  const {context, page, pageErrors} = await newPage(390, 844);
  await page.addScriptTag({path: require.resolve("axe-core")});
  const scan = async state => {
    const results = await page.evaluate(async () => window.axe.run(document, {
      runOnly: {type: "rule", values: ["color-contrast"]}
    }));
    const violations = results.violations.map(item => ({
      id: item.id,
      nodes: item.nodes.map(node => ({
        target: node.target,
        summary: node.failureSummary
      }))
    }));
    const incomplete = results.incomplete
      .filter(item => item.id === "color-contrast")
      .flatMap(item => item.nodes.map(node => ({
        target: node.target,
        summary: node.failureSummary,
        checks: [...(node.any || []), ...(node.all || []), ...(node.none || [])]
          .map(check => ({id: check.id, message: check.message, data: check.data}))
      })));
    console.log("WCAG text contrast", state, JSON.stringify({
      passes: results.passes.filter(item => item.id === "color-contrast").length,
      incomplete,
      violations
    }));
    assert.deepEqual(violations, [], state + " text contrast violations");
  };

  await scan("mobile navigation closed");
  await page.locator("#mobile-menu").click();
  await scan("mobile navigation open");
  await page.setViewportSize({width: 1280, height: 900});
  await scan("desktop");
  assert.deepEqual(pageErrors, []);
  await context.close();
});
