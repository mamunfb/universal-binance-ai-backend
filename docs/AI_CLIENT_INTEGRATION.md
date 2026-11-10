# AI Client Integration and API Operations

This backend exposes a REST API and an OpenAPI document so different AI clients can inspect the same machine-readable contract.

## API discovery

- OpenAPI JSON: `GET /openapi.json`
- Interactive Swagger UI: `GET /docs`
- ReDoc: `GET /redoc`

For a hosted deployment, replace `BASE_URL` below with the HTTPS origin of that deployment. Do not expose a development server directly to the public internet.

## Minimal client flow

1. Fetch `/openapi.json` and inspect the operation, query parameters, defaults, and bounds before calling an endpoint.
2. Call only the required read-only endpoint. Public market endpoints do not need a Binance API secret.
3. Parse the JSON response and inspect its `status`, source, timestamps, coverage, and warning fields where present.
4. Treat `INCOMPLETE`, `UNKNOWN`, empty results, and missing coverage as uncertainty—not as zero activity or confirmation that no event occurred.
5. Preserve the response's `X-Request-ID` header for troubleshooting. Error bodies also include `request_id`.

Example:

```bash
curl --fail-with-body -sS \
  -H 'Accept: application/json' \
  'https://YOUR_API_HOST/api/v1/markets/spot/klines/BTCUSDT?interval=1h&limit=100'
```

## Error contract

Errors use this envelope:

```json
{
  "status": "FAILED",
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request parameters or body failed validation.",
    "details": []
  },
  "request_id": "server-generated-id"
}
```

The `details` field is optional and can be a list or object. Validation details deliberately omit submitted input values. Clients should branch on the HTTP status and stable `error.code`, not parse human-readable message text. A generic 500 response does not reveal internal exception details.

Common codes include `VALIDATION_ERROR`, `NOT_FOUND`, `UNAUTHORIZED`, `FORBIDDEN`, `RATE_LIMITED`, `UPSTREAM_ERROR`, `UPSTREAM_TIMEOUT`, `SERVICE_UNAVAILABLE`, and `INTERNAL_SERVER_ERROR`. Not every deployment enables authentication or rate limiting; the presence of a code does not imply that a feature is configured.

## Retry guidance

- Do not automatically retry 400, 401, 403, 404, or 422 without changing the request or credentials.
- For 429, honor `Retry-After` when the deployment supplies it; otherwise use exponential backoff with jitter and a bounded retry count.
- For 502, 503, and 504, retry only idempotent GET requests, with a bounded backoff. Do not assume a failed upstream request means the upstream operation did not occur.
- Do not blindly retry POST requests such as historical indexing unless the endpoint's documented idempotency and retry behavior has been reviewed. The ERC-20 indexer is designed to safely replay already indexed ranges, but callers must still respect range limits.
- Avoid parallel request bursts. Cache responses only for a duration appropriate to the endpoint's freshness and purpose.

## Rate limiting and deployment boundary

This application currently standardizes the 429 error code but does not implement a distributed application-level rate limiter. Do not interpret the error handler as proof that rate limiting is active.

For a public deployment, configure request limits at a trusted edge proxy or API gateway (for example, a reverse proxy or managed gateway) and apply limits by client identity where authentication exists. Configure separate limits for expensive RPC/indexing routes and lightweight read routes. Ensure the proxy overwrites or safely validates forwarded client-IP headers; do not trust arbitrary client-supplied forwarding headers. If multiple application replicas are used, use a shared limiter at the gateway or a shared store rather than a per-process in-memory counter.

Set and publish operational limits based on measured provider quotas and load tests. No universal requests-per-minute value is specified here because it depends on the chosen host, upstream provider plan, route cost, and deployment topology.

## AI-client safety and interpretation

- The API is research-only. It does not place orders, withdraw assets, or execute trades.
- Do not provide private exchange keys, wallet seed phrases, or signing keys to an AI client or this service.
- Use HTTPS for deployed endpoints.
- Keep RPC provider credentials in server-side environment variables; never put them in prompts, client-side code, or public repository files.
- AI clients should preserve source, generated time, snapshot block, freshness, indexed coverage, and limitations when summarizing results.
- Net transfer flow is not equivalent to buying/selling, wallet balance, or intent. Registry labels are operator-managed and only as reliable as their evidence.
- A generated analysis is not a probability, guarantee, or financial recommendation.

## Compatibility boundary

OpenAPI describes the HTTP contract, not a guarantee that every AI product can call arbitrary URLs directly. A client may need an HTTP tool, connector, custom action, or a separately configured MCP adapter. The repository's REST API remains the canonical interface; do not assume an MCP server is deployed unless it is separately configured and documented.
