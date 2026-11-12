# Cloudflare Edge Rate Limiting — Deployment Guide

## Purpose

Apply rate limits at Cloudflare before requests reach the private FastAPI service. This protects the origin across multiple backend instances without relying on per-process memory.

## Deployment prerequisites

- A Cloudflare zone with the API hostname proxied through Cloudflare (orange cloud).
- A stable API hostname, for example `api.example.com`.
- The backend origin must not remain publicly reachable as an unrestricted bypass. Restrict origin ingress to Cloudflare where the hosting platform supports it, or use Cloudflare Tunnel / authenticated origin access.
- Keep FastAPI Bearer authentication enabled. Edge rate limiting is an additional layer, not a replacement.
- Do not put API keys in dashboard JavaScript, URLs, query strings, or rate-limit expressions.

## Suggested starting rules

Create a Cloudflare WAF custom rate limiting rule scoped to the API hostname and `/api/*` path.

### Rule A — general API traffic

- Expression: `http.host eq "api.example.com" and starts_with(http.request.uri.path, "/api/")`
- Counting characteristic: source IP address.
- Starting threshold: 120 requests per 60 seconds per IP.
- Action: Block for 60 seconds.
- Position: before any broad allow rule.

### Rule B — expensive scan / analysis endpoints

Create a stricter rule for known expensive endpoints only after confirming their exact paths in the current OpenAPI schema.

- Counting characteristic: source IP address.
- Starting threshold: 10 requests per 60 seconds per IP.
- Action: Managed challenge or block for 60 seconds, depending on whether the callers are browser-based or server-to-server.
- Do not assume these example thresholds are optimal; tune them from observed legitimate usage and Cloudflare plan capabilities.

## Important caveats

- Cloudflare rate limiting capabilities, rule counts, counting characteristics, and plan availability vary by plan and may change. Confirm the options shown in the actual zone dashboard before applying.
- IP-based limits can affect multiple users behind NAT and can be evaded by distributed sources. They are a first-line abuse control, not identity-level quotas.
- Do not trust arbitrary client-supplied `CF-Connecting-IP` headers at the origin. Trust them only when requests are guaranteed to arrive from Cloudflare.
- If a Cloudflare rule cannot count by a verified authenticated identity, retain application authentication and consider a shared Redis-backed limiter for per-client quotas.
- Return/observe HTTP 429 behavior and `Retry-After` where supported. Clients should use bounded backoff and avoid retry storms.
- Test with a low temporary threshold in a staging hostname first. Confirm legitimate calls, 429/block behavior, and that direct-origin requests cannot bypass the edge.

## Acceptance checklist

1. HTTPS works on the proxied API hostname.
2. Requests without a valid Bearer key still receive 401 from the application.
3. A temporary low threshold produces the expected edge limit response.
4. Normal dashboard and AI-client workflows remain usable.
5. The backend origin cannot be reached through an unrestricted public route.
6. Cloudflare event logs show the expected rule and counting characteristic.

## Current status

This file is a deployment runbook only. No Cloudflare zone, DNS record, WAF rule, origin restriction, or live deployment has been changed by this commit. Obtain explicit approval and zone access before applying changes.
