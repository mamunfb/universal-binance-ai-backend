"""Regression tests for dashboard backend URL and request hardening."""

from pathlib import Path
import subprocess
import textwrap


def test_dashboard_api_url_validation_and_request_runtime():
    html = (Path(__file__).resolve().parents[1] / "dashboard" / "index.html").read_text()
    harness = textwrap.dedent(r"""
        const assert = require("node:assert/strict");
        const vm = require("node:vm");
        let source = "";
        process.stdin.setEncoding("utf8");
        process.stdin.on("data", chunk => source += chunk);
        process.stdin.on("end", () => {
          (async () => {
            const match = source.match(/<script>([\s\S]*?)<\/script>/i);
            assert.ok(match, "dashboard inline script missing");
            const elements = new Map();
            const document = {
              getElementById(id) {
                if (!elements.has(id)) elements.set(id, {
                  value: "", innerHTML: "", textContent: "", onclick: null, style: { display: "" }
                });
                return elements.get(id);
              }
            };
            const requests = [];
            let response = { ok: true, status: 200, json: async () => ({ ready: true }) };
            const fetch = async (url, options) => {
              requests.push({ url, options });
              return response;
            };
            const context = {
              document,
              window: { location: { origin: "https://dashboard.example" } },
              URL, URLSearchParams, fetch
            };
            vm.runInNewContext(match[1] + "\nglobalThis.__callForTest = call;", context);
            const call = context.__callForTest;
            const base = document.getElementById("base");
            const key = document.getElementById("key");

            await assert.rejects(call("/health"), /Backend Base URL required/);
            base.value = "https://api.example";
            await assert.rejects(call("/health"), /Bearer API key/);
            assert.equal(requests.length, 0, "missing API key must not send a request");

            key.value = " private-test-key ";
            for (const url of [
              "http://api.example",
              "ftp://api.example",
              "https:/api.example",
              "https:api.example",
              "https:\\api.example",
              "https://api.example\\path",
              "https://user:pass@api.example",
              "https://@api.example",
              "https://api.example?",
              "https://api.example#",
              "https://api.example/path?x=1",
              "https://api.example/path#fragment"
            ]) {
              base.value = url;
              await assert.rejects(call("/health"), /Backend Base URL|HTTPS is required/,
                "must reject unsafe URL: " + url);
            }
            assert.equal(requests.length, 0, "rejected URLs must never reach fetch");

            base.value = "http://localhost:8000/api/";
            await call("/health");
            assert.equal(requests[0].url, "http://localhost:8000/api/health");

            base.value = "http://127.0.0.1:8000";
            await call("/health");
            assert.equal(requests[1].url, "http://127.0.0.1:8000/health");

            base.value = "http://[::1]:8000";
            await call("/health");
            assert.equal(requests[2].url, "http://[::1]:8000/health");

            base.value = "https://api.example/v1/";
            await call("/health", {
              method: "POST",
              body: JSON.stringify({ confirm: true }),
              headers: {
                Authorization: "Bearer caller-override",
                "Content-Type": "text/plain",
                "X-Test": "preserved"
              }
            });
            assert.equal(requests[3].url, "https://api.example/v1/health");
            assert.equal(requests[3].options.headers.Authorization, "Bearer private-test-key");
            assert.equal(requests[3].options.headers["Content-Type"], "application/json");
            assert.equal(requests[3].options.headers["X-Test"], "preserved");
            assert.equal(requests[3].options.method, "POST");
            assert.equal(requests[3].options.body, JSON.stringify({ confirm: true }));
            assert.equal(requests[3].url.includes("private-test-key"), false);

            response = { ok: true, status: 200, json: async () => null };
            await assert.rejects(call("/health"), /invalid JSON object/);
            response = { ok: true, status: 200, json: async () => [] };
            await assert.rejects(call("/health"), /invalid JSON object/);
            response = { ok: true, status: 200, json: async () => ({ ready: true }) };

            response = { ok: false, status: 401, json: async () => ({ detail: "Unauthorized" }) };
            await assert.rejects(call("/health"), /Unauthorized/);
            response = { ok: false, status: 502, json: async () => { throw Error("not JSON"); } };
            await assert.rejects(call("/health"), /non-JSON response \(HTTP 502\)/);
          })().catch(error => { console.error(error); process.exitCode = 1; });
        });
    """)
    result = subprocess.run(
        ["node", "-e", harness],
        input=html,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
