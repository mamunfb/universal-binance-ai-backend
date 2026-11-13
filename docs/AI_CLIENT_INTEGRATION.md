# Personal AI Client Integration

## Scope

This is a private, single-owner project for the repository owner. The only AI clients in scope are:

1. ChatGPT
2. Google Gemini
3. Manus
4. Claude
5. Perplexity

Do not build a public SaaS, customer registration, subscription, billing, tenant management, or public API marketplace for this project. Do not add integrations for other AI products unless the owner explicitly changes this scope.

The five AI clients share one canonical backend and one research-only crypto intelligence engine. They do not each get separate market-data or on-chain implementations.

## Shared architecture

```text
Binance public data + configured EVM RPC providers
                    |
          Provider / analysis services
                    |
        Personal Crypto Intelligence Engine
                    |
             Canonical REST API
                    |
        +-----------+-----------+
        |           |           |
     ChatGPT   Gemini   Manus   Claude   Perplexity
     adapter   adapter  adapter  adapter   adapter
        |         |        |        |         |
        +---------- Owner-only access --------+
```

REST/OpenAPI is the canonical API contract. MCP may be used as a shared tool interface where a target client supports the required MCP transport and authentication. Client-specific adapters should remain thin: translate tool calls and arguments, call the same REST services, and return the same structured evidence and limitations.

## Client integration policy

- **ChatGPT:** use an OpenAPI-based custom action or another supported private tool connection when available. Expose only required read-only operations.
- **Google Gemini:** use function/tool declarations or a supported connector that calls the same private REST API. Keep provider credentials on the backend.
- **Manus:** use a supported MCP or HTTP/API integration if available in the selected Manus environment. Confirm the actual supported transport and authentication before implementing its adapter; do not assume every Manus plan or workspace exposes the same integration features.
- **Claude:** use a supported MCP connection or API/tool integration available in the selected Claude product. Verify the target product's transport and authentication requirements before implementation.
- **Perplexity:** use a supported API or connector/tool integration for the selected Perplexity product. Do not assume the consumer search interface accepts arbitrary private MCP servers; verify the exact target product and plan first.

Platform capabilities and plan availability can change. A platform is not considered integrated until a real end-to-end connection test succeeds in the owner's account.

## API discovery

- OpenAPI JSON: `GET /openapi.json`
- Interactive Swagger UI: `GET /docs`
- ReDoc: `GET /redoc`

For a hosted deployment, use its HTTPS origin. Do not expose a development server directly to the public internet.

## Minimal client flow

1. Discover the operation and parameter bounds from `/openapi.json`.
2. Call only the necessary read-only endpoint.
3. Inspect `status`, source, generated time, snapshot block, freshness, indexed coverage, and warning fields where present.
4. Treat `INCOMPLETE`, `UNKNOWN`, empty results, and missing coverage as uncertainty—not as zero activity or proof that no event occurred.
5. Preserve `X-Request-ID` for troubleshooting. Error bodies also include `request_id`.

Example:

```bash
curl --fail-with-body -sS \
  -H 'Accept: application/json' \
  'https://YOUR_PRIVATE_API_HOST/api/v1/markets/spot/klines/BTCUSDT?interval=1h&limit=100'
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

The `details` field is optional and can be a list or object. Validation details omit submitted input values. Clients should branch on HTTP status and stable `error.code`, not parse human-readable message text. Generic 500 responses do not expose internal exception text.

Common codes include `VALIDATION_ERROR`, `NOT_FOUND`, `UNAUTHORIZED`, `FORBIDDEN`, `RATE_LIMITED`, `UPSTREAM_ERROR`, `UPSTREAM_TIMEOUT`, `SERVICE_UNAVAILABLE`, and `INTERNAL_SERVER_ERROR`. Not every deployment enables authentication or rate limiting; the presence of an error code does not mean the feature is configured.

## MCP adapter response handling

The local MCP adapter exposes a read-only `get_stored_historical_klines` tool for locally collected candles. The local historical collector itself is available through the authenticated REST POST endpoint, not through MCP. The adapter preserves successful JSON objects exactly, including source, generated timestamps, freshness, coverage, missing-data, and warning fields. For HTTP failures it returns a normalized object with `status: FAILED`, `http_status`, a stable `error.code`, a safe message, and a `retryable` flag. It also carries the API `request_id` when supplied. Connection failures use `UPSTREAM_CONNECTION_ERROR`; invalid or non-object success JSON uses `UPSTREAM_INVALID_RESPONSE`. These normalized MCP errors are adapter output and do not change the canonical REST API error contract. Retry only when `retryable` is true and apply bounded backoff; do not retry authentication or validation failures unchanged.

## Retry guidance

- Do not automatically retry 400, 401, 403, 404, or 422 without changing the request or credentials.
- For 429, honor `Retry-After` when supplied; otherwise use bounded exponential backoff with jitter.
- For 502, 503, and 504, retry only idempotent GET requests with bounded backoff.
- Do not blindly retry POST requests. The ERC-20 indexer supports safe replay of already indexed ranges, but callers must respect documented range limits.
- Avoid parallel request bursts. Cache only according to the endpoint's freshness requirements.

## Private access and security

- The intended user is one owner. Do not create public sign-up or multi-customer account flows.
- API routes under `/api/` require a Bearer key whenever `PERSONAL_API_KEY` or `AI_CLIENT_API_KEYS` is configured; the supported client identities are `chatgpt`, `gemini`, `manus`, `claude`, and `perplexity`.
- Set `APP_ENV=production` and `PERSONAL_API_KEY` to a randomly generated secret of at least 32 characters before production deployment. Production API requests fail closed with 503 if a sufficiently long key is not configured.
- In development, an empty `PERSONAL_API_KEY` leaves API routes unauthenticated for local testing only. Never expose that configuration to the public internet.
- Example environment configuration (use your own secret; do not commit it):

```env
APP_ENV=production
PERSONAL_API_KEY=replace-with-a-unique-random-secret-at-least-32-characters
```

- Example request:

```bash
curl -H "Authorization: Bearer $PERSONAL_API_KEY" \
  "https://YOUR_PRIVATE_API_HOST/api/v1/analysis/futures/liquidations/status"
```

- Protect the private API with server-side authentication before exposing it beyond localhost/private network.
- Configure separate keys for the five supported AI clients with `AI_CLIENT_API_KEYS`, a JSON object mapping `chatgpt`, `gemini`, `manus`, `claude`, and `perplexity` to independent random secrets of at least 32 characters.
- Example only (replace every value with a unique randomly generated secret; never commit real secrets):

```env
APP_ENV=production
AI_CLIENT_API_KEYS={"chatgpt":"REPLACE_WITH_CHATGPT_RANDOM_SECRET_32_CHARS_MIN","gemini":"REPLACE_WITH_GEMINI_RANDOM_SECRET_32_CHARS_MIN","manus":"REPLACE_WITH_MANUS_RANDOM_SECRET_32_CHARS_MIN","claude":"REPLACE_WITH_CLAUDE_RANDOM_SECRET_32_CHARS_MIN","perplexity":"REPLACE_WITH_PERPLEXITY_RANDOM_SECRET_32_CHARS_MIN"}
```

- Production requires either all five valid per-client keys or a strong owner-level `PERSONAL_API_KEY`. The owner key can be used for administration; prefer the individual client keys for AI integrations.
- During development, an empty key configuration leaves API routes unauthenticated for local testing only. Never expose that configuration to the public internet.
- Each client key can be revoked or rotated independently by changing its environment value and restarting/redeploying the service.
- Never commit raw credentials.
- Do not put private API credentials, RPC provider secrets, Binance secrets, wallet seed phrases, or signing keys in prompts or client-side code.
- Prefer HTTPS. Restrict network access at the deployment boundary where possible.
- Keep request logs free of Authorization headers, API keys, and sensitive query values.

## Rate limiting and deployment boundary

The application standardizes the 429 error code but does not yet implement a distributed application-level rate limiter. Do not interpret the error handler as proof that rate limiting is active.

For a private deployment, configure limits at a trusted reverse proxy or gateway. Apply separate limits to expensive RPC/indexing routes and lightweight reads. If multiple application replicas are used, use a shared gateway/store rather than a per-process in-memory counter. Trust only proxy-controlled client identity headers.

Do not choose a fixed requests-per-minute limit until the deployment, upstream quotas, and actual workload are known.

## Research-only constraints

- No order placement, withdrawals, signing, or trading execution.
- Public market data does not require a Binance API secret.
- Net token transfer flow is not equivalent to buying/selling, wallet balance, or intent.
- Registry labels are operator-managed and only as reliable as their evidence.
- AI summaries must retain source, timestamps, coverage, freshness, and limitations.
- Do not present unvalidated scores as probabilities, guarantees, or financial recommendations.

## Completion criteria

A ChatGPT, Gemini, Manus, Claude, or Perplexity adapter is complete only after:
1. Its exact supported connection method is confirmed in the target account/environment.
2. It authenticates to the private backend without exposing credentials in prompts or client code.
3. It can discover/call a small set of read-only tools.
4. It preserves structured errors, request IDs, timestamps, and data-quality metadata.
5. End-to-end tests pass for success, validation failure, authentication failure, and unavailable upstream data.


## Private MCP stdio adapter

A first shared MCP adapter is available at `mcp-server/server.py`. It exposes a small, read-only set of tools that call the canonical REST API; it does not duplicate market or on-chain analysis logic.

Install dependencies with `pip install -r requirements.txt`. Run a separate local MCP process for each AI client, setting these environment variables in that client's MCP server configuration:

```env
PERSONAL_API_BASE_URL=https://YOUR_PRIVATE_API_HOST
MCP_CLIENT_NAME=chatgpt
AI_CLIENT_API_KEYS={"chatgpt":"YOUR_CHATGPT_SECRET","gemini":"YOUR_GEMINI_SECRET","manus":"YOUR_MANUS_SECRET","claude":"YOUR_CLAUDE_SECRET","perplexity":"YOUR_PERPLEXITY_SECRET"}
APP_ENV=production
```

Change `MCP_CLIENT_NAME` to `gemini`, `manus`, `claude`, or `perplexity` for the other local processes. The process selects only its matching key and sends it as a Bearer token. Do not paste secrets into prompts, commit them, or place them in a shared public configuration. Use the client's secure local environment/secret facility.

Example local command:

```bash
python mcp-server/server.py
```

The adapter uses MCP stdio transport, so the AI client must support launching a local MCP server process. A remote-only client cannot use this stdio process directly; use a separately secured remote MCP gateway only after validating that client's supported transport. The presence of this adapter does not establish that any of the five AI accounts is already connected.

Available tools:
- `get_spot_klines`
- `get_spot_technical_analysis`
- `get_futures_derivatives`
- `get_spot_futures_basis`
- `get_market_evidence_snapshot`
- `get_news_intelligence`
- `get_cross_chain_token_intelligence`
- `get_stored_historical_klines`
- `inspect_historical_kline_coverage`
- `get_historical_collector_status`
- `get_derivatives_collector_status`
- `get_stored_funding_rate_history`
- `get_stored_open_interest_history`
- `analyze_funding_open_interest`
- `analyze_advanced_derivatives`
- `analyze_multi_timeframe_derivatives`
- `get_stored_derivatives_ratio_history`
- `analyze_combined_derivatives_intelligence`
- `get_derivatives_signal_history`
- `evaluate_historical_signal_performance`
- `analyze_smart_money_market_structure`
- `analyze_order_book_liquidity`
- `analyze_liquidity_sweep_confirmation`
- `analyze_market_structure_confluence`
- `save_market_confluence_snapshot`
- `get_market_confluence_history`
- `evaluate_market_confluence_performance`
- `get_liquidation_collector_status`

All tools are non-trading. The confluence snapshot save tool writes only local research snapshots; no exchange order, signing, withdrawal, or trade execution tool is exposed. MCP tool access remains subject to the backend's API authentication and route availability.


### Historical market regime

The read-only MCP tool `analyze_historical_market_regime` calls
`GET /api/v1/analysis/market-regime/{market}/{symbol}` and reads only locally
stored candles. It does not trigger data collection. See
`docs/MARKET_REGIME_ANALYSIS.md` for the fixed heuristic and its limitations.


### Liquidation cluster analysis

The read-only MCP tool `analyze_liquidation_clusters` calls
`GET /api/v1/analysis/futures/liquidation-clusters/{symbol}`. It groups
locally stored force-order snapshots into price buckets and reports event
coverage and limitations. It does not collect events. See
`docs/LIQUIDATION_CLUSTER_ANALYSIS.md`.



## Historical signal performance evaluation

The read-only endpoint `GET /api/v1/analysis/derivatives/signal-performance/{symbol}` evaluates forward 1h/4h/24h price outcomes for locally stored completed descriptive snapshots. It reports sample sizes, gross/hypothetical net returns and favorable/adverse excursions. It does not calculate directional accuracy or claim a strategy win rate because the stored classifications do not define validated directional entries. The MCP tool is `evaluate_historical_signal_performance`. See `docs/HISTORICAL_SIGNAL_PERFORMANCE.md` for the method and coverage caveats.


### Smart Money market structure

The read-only MCP tool `analyze_smart_money_market_structure` calls
`GET /api/v1/analysis/smart-money-structure/{market}/{symbol}`. It analyzes locally stored OHLCV candles for swing points, BOS/CHoCH, liquidity-sweep candidates, FVG candidates, order-block candidates and sample-range premium/discount. All are heuristic candidates rather than verified institutional order flow. See `docs/SMART_MONEY_MARKET_STRUCTURE.md`.


### Order book liquidity intelligence

The read-only MCP tool `analyze_order_book_liquidity` calls
`GET /api/v1/analysis/order-book/{market}/{symbol}`. It fetches a single public
REST snapshot and calculates spread, visible depth, imbalance, microprice,
near-mid bands and relative large-order candidates. It is not a sequence-aware
WebSocket stream or historical liquidity tracker. See
`docs/ORDER_BOOK_LIQUIDITY_INTELLIGENCE.md`.


### Stored order-book liquidity history

- `get_order_book_stream_status` reports whether the optional local depth collector is enabled and synchronized.
- `get_stored_order_book_history` reads locally captured samples by market and symbol.
- The collector is disabled by default. Enable it only on a persistent, single-process deployment with explicit `ORDER_BOOK_COLLECTOR_JOBS`.
- History begins at deployment/enablement and is sampled periodically; it is not exchange-wide historical backfill.


### Liquidity behavior and aggregate trade flow

- `get_aggregate_trade_collector_status` reports the optional trade stream collector state.
- `get_stored_aggregate_trades` reads locally stored public aggregate trades.
- `analyze_liquidity_behavior` compares the latest two sampled order-book snapshots with trades in that interval and reports candidate liquidity withdrawal/absorption patterns.\n- `analyze_order_flow_intelligence` calculates local aggregate-trade volume profile (POC/VAH/VAL), window-relative CVD, and price/CVD divergence candidates. It reads stored trades only; see `docs/ORDER_FLOW_INTELLIGENCE.md`.
- Enable the aggregate-trade collector separately from the order-book collector. Both must be enabled for the same market/symbol to produce useful combined analysis.
- Results are heuristic candidates only; no proof of spoofing, manipulation, or institutional activity is claimed.


### Multi-timeframe order flow

The read-only MCP tool `analyze_multi_timeframe_order_flow` calls
`GET /api/v1/analysis/order-flow/multi-timeframe/{market}/{symbol}`.
It compares locally stored aggregate-trade CVD and volume-profile context
across selected rolling windows. Overlapping windows are not independent
confirmations. See `docs/MULTI_TIMEFRAME_ORDER_FLOW.md`.


### Liquidity sweep confirmation

The read-only MCP tool `analyze_liquidity_sweep_confirmation` calls
`GET /api/v1/analysis/liquidity-sweep-confirmation/{market}/{symbol}`.
It correlates OHLC wick/reclaim candidates and equal swing zones with
locally captured aggregate trades, paired sampled order-book depth, and
nearest timestamp-aligned USD-M OI/funding context. Missing or stale
derivatives observations remain null; they are not forward-filled. The
evidence labels are heuristic classifications, not probabilities or
validated trade signals. See `docs/LIQUIDITY_SWEEP_CONFIRMATION.md`.


### Market structure + order flow confluence

The read-only MCP tool `analyze_market_structure_confluence` calls
`GET /api/v1/analysis/market-structure-confluence/{market}/{symbol}`.
It summarizes local market structure, market regime, one-hour CVD,
multi-timeframe flow and liquidity-sweep evidence. It reports agreement,
conflicts and coverage; missing or neutral sources do not vote against
available directional evidence. The output is descriptive, not a probability
or trading recommendation. See `docs/MARKET_STRUCTURE_CONFLUENCE.md`.


### Confluence snapshot history

MCP tools: `save_market_confluence_snapshot`, `get_market_confluence_history`, and `evaluate_market_confluence_performance`. They save/read descriptive snapshots and evaluate later local candle movement. This is not a strategy backtest or validated win rate. See `docs/MARKET_STRUCTURE_CONFLUENCE.md`.


The confluence outcome evaluator returns seven horizons: 1h, 4h, 24h, 48h, 72h, 15 days (360h), and 30 days (720h). Its default candle resolution is 1h to preserve hourly comparison over the full 30-day period. The 30-day horizon is fixed-duration, not a calendar month. The response includes per-horizon sample maturity and local candle coverage.
