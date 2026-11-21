"use strict";

const http = require("node:http");
const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "../dashboard");
const assetPrefix = "/dashboard-assets/";
const types = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8"
};

function createDashboardQaServer() {
  return http.createServer((req, res) => {
    let pathname;
    try {
      pathname = decodeURIComponent(new URL(req.url, "http://127.0.0.1").pathname);
    } catch {
      res.writeHead(400, { "cache-control": "no-store" }).end("Bad request");
      return;
    }

    let relativePath;
    if (pathname === "/" || pathname === "/dashboard" || pathname === "/dashboard/") {
      relativePath = "index.html";
    } else if (pathname.startsWith(assetPrefix)) {
      // Dashboard HTML uses /dashboard-assets/<file>, while files live
      // directly in the repository's dashboard/ directory.
      relativePath = pathname.slice(assetPrefix.length);
    } else {
      relativePath = pathname.replace(/^\/+/, "");
    }

    const target = path.resolve(root, relativePath);
    if (target === root) {
      res.writeHead(404, { "cache-control": "no-store" }).end("Not found");
      return;
    }
    if (!target.startsWith(root + path.sep)) {
      res.writeHead(403, { "cache-control": "no-store" }).end("Forbidden");
      return;
    }

    fs.readFile(target, (error, data) => {
      if (error) {
        res.writeHead(404, {
          "cache-control": "no-store",
          "x-content-type-options": "nosniff"
        }).end("Not found");
        return;
      }
      res.writeHead(200, {
        "content-type": types[path.extname(target)] || "application/octet-stream",
        "cache-control": "no-store",
        "x-content-type-options": "nosniff"
      });
      res.end(data);
    });
  });
}

if (require.main === module) {
  createDashboardQaServer().listen(4173, "127.0.0.1", () => {
    process.stdout.write("Dashboard QA server listening on 4173\n");
  });
}

module.exports = { createDashboardQaServer };
