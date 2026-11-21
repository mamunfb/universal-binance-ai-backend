"use strict";

const { test, before, after } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const http = require("node:http");
const { createDashboardQaServer } = require("./serve_dashboard_qa.cjs");

const dashboardRoot = path.resolve(__dirname, "../dashboard");
let server;
let origin;

before(async () => {
  server = createDashboardQaServer();
  await new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", resolve);
  });
  origin = "http://127.0.0.1:" + server.address().port;
});

after(async () => {
  if (server) await new Promise((resolve, reject) => {
    server.close(error => error ? reject(error) : resolve());
  });
});

function get(pathname) {
  return new Promise((resolve, reject) => {
    http.get(origin + pathname, response => {
      const chunks = [];
      response.on("data", chunk => chunks.push(chunk));
      response.on("end", () => resolve({
        status: response.statusCode,
        headers: response.headers,
        body: Buffer.concat(chunks)
      }));
    }).on("error", reject);
  });
}

for (const [asset, contentType] of [
  ["app.css", "text/css; charset=utf-8"],
  ["chart.js", "text/javascript; charset=utf-8"],
  ["app.js", "text/javascript; charset=utf-8"]
]) {
  test("serves /dashboard-assets/" + asset + " from dashboard root", async () => {
    const response = await get("/dashboard-assets/" + asset);
    assert.equal(response.status, 200);
    assert.equal(response.headers["content-type"], contentType);
    assert.equal(response.headers["x-content-type-options"], "nosniff");
    assert.deepEqual(response.body, fs.readFileSync(path.join(dashboardRoot, asset)));
  });
}

test("serves Dashboard HTML at the local QA root", async () => {
  const response = await get("/");
  assert.equal(response.status, 200);
  assert.match(response.headers["content-type"], /^text\/html; charset=utf-8$/);
  assert.match(response.body.toString("utf8"), /\/dashboard-assets\/app\.css/);
});

test("does not expose a dashboard asset directory listing", async () => {
  const response = await get("/dashboard-assets/");
  assert.equal(response.status, 404);
});

test("does not allow traversal outside the dashboard root", async () => {
  const response = await get("/dashboard-assets/%252e%252e/backend/app/main.py");
  assert.ok([403, 404].includes(response.status));
  assert.doesNotMatch(response.body.toString("utf8"), /FastAPI|from fastapi import/);
});
