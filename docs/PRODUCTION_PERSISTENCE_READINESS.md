# Production Persistence and Deployment Readiness

## Current persistence split

The repository currently has two separate persistence paths:

1. The scheduled collector in `scripts/hourly_market_scan.py` writes its run envelope to Neon/PostgreSQL in the `market_scan_runs` table. This stores the three market collector responses (Spot, USD-M and COIN-M) as JSONB.
2. Dashboard market-confluence snapshots use PostgreSQL/Neon when `DATABASE_URL` is configured, through the `MarketConfluenceStore` adapter; they fall back to local SQLite when it is absent (for local development/tests).
3. Other historical collectors still use local SQLite files configured through `*_DATABASE_PATH` settings. These include historical klines, funding rates, open interest, derivatives ratios/signals, order-book samples, aggregate trades, and EVM transfer data.

These are not interchangeable stores. The scheduled scan's PostgreSQL row is not currently read by the dashboard's market-confluence history endpoints.

## Market-confluence PostgreSQL migration and integration test

- The canonical schema is checked in at `migrations/001_market_confluence_snapshots.sql`. Apply it to the target Neon database/branch before enabling the PostgreSQL adapter.
- For a real, isolated integration check, set `TEST_DATABASE_URL` to a disposable database/branch where that migration has been applied, then run:
  `pytest -q tests/test_market_confluence_postgres_integration.py`
- The integration test creates a uniquely named test symbol, verifies save/get/history, and deletes its test row in a `finally` block. Do not point it at a production database; use a disposable branch.
- Without `TEST_DATABASE_URL`, the integration test is skipped. The ordinary CI suite therefore verifies the SQLite path and mocked PostgreSQL adapter, not live Neon connectivity.
- Keep `DATABASE_URL` and `TEST_DATABASE_URL` in provider/CI secret storage. Never commit connection strings or paste them into source files.

## Cloud deployment constraint

A container's writable local filesystem must not be treated as durable storage across Cloud Run instance replacement, scale-to-zero, or redeployment. Therefore, deploying the current SQLite-backed collectors and dashboard history endpoints to Cloud Run without a persistence redesign can cause history to be unavailable or split between instances.

Do not mark production persistence complete merely because the API container starts or because scheduled market scans insert rows into Neon.

## Required production design before enabling durable dashboard history

- Verify the configured Neon-backed market-confluence snapshot adapter with a real insert/read test against a disposable database or branch; keep the SQLite fallback for local development/tests.
- Decide whether the hourly/scheduled market scan envelope should feed the dashboard directly, or whether a separate normalized confluence snapshot is required. The existing collector output is raw market coverage, not the same data contract as a confluence snapshot.
- Migrate the remaining SQLite-backed collectors individually; do not blindly replace SQLite with PostgreSQL without checking each store's schema, transaction semantics, retention, and concurrency behavior.
- Add migration/version management, connection pooling or bounded connection usage, indexes, backup/restore verification, and integration tests against a disposable PostgreSQL database.
- Keep SQLite for local development and unit tests if useful, with an explicit storage adapter boundary.

## Operational checklist

- Set `APP_ENV=production` and configure a strong `PERSONAL_API_KEY` (at least 32 characters) or all five independent `AI_CLIENT_API_KEYS` before exposing the API.
- Store credentials only in the hosting provider's secret manager; never commit them or place them in dashboard JavaScript.
- Configure `DATABASE_URL` as a provider secret for scheduled scans. The collector currently fails if this secret is absent.
- Verify the official Binance endpoints from the actual deployment region. HTTP 403/451 and other access restrictions must be reported as unavailable; do not attempt to bypass them.
- Verify `/health`, authenticated API success, unauthenticated API rejection, Neon insert/read, and restart/redeployment persistence before production acceptance.
- Configure a trusted gateway or edge rate limit. The application documents 429 errors but does not currently provide a distributed application-level rate limiter.
- Use HTTPS and restrict the API to intended private clients.

## Current readiness statement

The repository has automated backend tests, dashboard JavaScript syntax validation, and a Docker image build in CI. These checks do not prove live Binance reachability, Neon connectivity from the deployment, durable SQLite history, Cloudflare routing, or end-to-end AI-client connectivity. Those remain explicit acceptance tests.
