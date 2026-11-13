"""Exercise dashboard API request behavior in the JavaScript runtime."""

from pathlib import Path
import subprocess
import textwrap


def test_dashboard_api_runtime_auth_transport_and_errors():
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
                value: "", innerHTML: "", textContent: "", onclick: null
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
          const window = { location: { origin: "https://dashboard.example" } };
          const context = { document, window, URL, URLSearchParams, fetch };
          vm.runInNewContext(match[1] + "\nglobalThis.__callForTest = call;", context);
          const call = context.__callForTest;
          const base = document.getElementById("base");
          const key = document.getElementById("key");

          await assert.rejects(call("/api/v1/research/preflight"), /Bearer API key/);
          assert.equal(requests.length, 0, "missing key must never make a request");

          key.value = "private-test-key";
          base.value = "http://api.example";
          await assert.rejects(call("/api/v1/research/preflight"), /HTTPS is required/);
          assert.equal(requests.length, 0, "insecure remote URL must never make a request");

          base.value = "https://api.example/v1/";
          const ok = await call("/api/v1/research/preflight");
          assert.equal(ok.ready, true);
          assert.equal(requests.length, 1);
          assert.equal(requests[0].url, "https://api.example/v1/api/v1/research/preflight");
          assert.equal(requests[0].options.headers.Authorization, "Bearer private-test-key");
          assert.equal(requests[0].options.headers["Content-Type"], "application/json");

          response = { ok: false, status: 401, json: async () => ({ detail: "Unauthorized" }) };
          await assert.rejects(call("/api/v1/research/preflight"), /Unauthorized/);

          response = { ok: false, status: 502, json: async () => { throw Error("not JSON"); } };
          await assert.rejects(call("/api/v1/research/preflight"), /non-JSON response \(HTTP 502\)/);
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
