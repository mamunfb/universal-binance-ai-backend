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

## Historical OHLCV storage migration — staged, not enabled

- A PostgreSQL target schema is available at `migrations/002_historical_klines.sql`.
- This migration is schema preparation only. `HistoricalKlineStore` still uses SQLite; applying the SQL does not switch application reads or writes to Neon.
- Before enabling a PostgreSQL adapter, preserve current validation and upsert semantics, implement `latest_open_time`, `history`, and `save_klines` parity, and add SQLite/PostgreSQL contract tests plus an opt-in disposable-database integration test.
- Do not claim durable OHLCV history until the application adapter is switched and insert/read/restart tests pass against PostgreSQL.

## Historical OHLCV PostgreSQL adapter

- `HistoricalKlineStore` now supports PostgreSQL when `HISTORICAL_KLINE_DATABASE_URL` or the shared `DATABASE_URL` is configured; otherwise it uses SQLite for local development/tests.
- Apply `migrations/002_historical_klines.sql` before enabling the PostgreSQL setting.
- The PostgreSQL adapter implements save/upsert, latest open-time lookup, and bounded history retrieval. Existing candle validation and idempotent conflict handling are retained.
- An opt-in real-database test is available at `tests/test_historical_klines_postgres_integration.py`; set `TEST_DATABASE_URL` to a disposable migrated database and run `pytest -q tests/test_historical_klines_postgres_integration.py`.
- The real database test is skipped when the secret is absent. CI success without that secret is not evidence of a live Neon connection.
- This adapter covers OHLCV only. Funding-rate, open-interest, derivatives, order-book, aggregate-trade, liquidation and EVM transfer stores remain separate migration work.

## Funding-rate and open-interest PostgreSQL adapters

- `FundingRateStore` and `OpenInterestStore` now support PostgreSQL using the shared `DATABASE_URL`; they retain SQLite fallback for local development/tests.
- Apply `migrations/003_funding_and_open_interest.sql` before enabling these PostgreSQL paths.
- Their save/upsert and history paths preserve symbol/market/period validation, idempotent keys, source labels, and observed-gap reporting.
- The opt-in real-database check is `tests/test_funding_open_interest_postgres_integration.py`; set `TEST_DATABASE_URL` to a disposable migrated database and run `pytest -q tests/test_funding_open_interest_postgres_integration.py`.
- Without the secret, the integration test is skipped. CI success alone does not prove live Neon connectivity.
- Other historical SQLite stores (derivatives ratios/signals, order-book, aggregate trades, liquidations, EVM transfers and remaining collectors) are not covered by these adapters.

## Derivatives ratios and signal snapshots

- `DerivativesRatioStore` supports PostgreSQL through `DATABASE_URL` and retains SQLite fallback. Apply `migrations/004_derivatives_ratio_history.sql` first.
- `DerivativesSignalStore` supports PostgreSQL through `DATABASE_URL` and retains SQLite fallback. Apply `migrations/005_derivatives_signal_snapshots.sql` first.
- Opt-in live-database tests: `tests/test_derivatives_ratio_postgres_integration.py` and `tests/test_derivatives_signal_postgres_integration.py`. Set `TEST_DATABASE_URL` to a disposable database with migrations 004 and 005 applied.
- These tests skip without `TEST_DATABASE_URL`; green ordinary CI does not verify live Neon connectivity.
- Order-book and aggregate-trade stream stores still use local SQLite and remain unsuitable for multi-instance durable production collection until migrated.

## Order-book and aggregate-trade stream persistence

- `OrderBookHistoryStore` and `AggregateTradeStore` now support PostgreSQL through `DATABASE_URL`, with SQLite fallback for local development.
- Apply `migrations/006_order_book_samples.sql` and `migrations/007_aggregate_trades.sql` before enabling the PostgreSQL-backed collectors.
- Order-book snapshots use a unique market/symbol/update ID and JSONB bid/ask arrays. Aggregate trades use unique market/symbol/trade ID and retain the normalized raw event payload as JSONB.
- Opt-in integration tests: `tests/test_order_book_postgres_integration.py` and `tests/test_aggregate_trade_postgres_integration.py`. Set `TEST_DATABASE_URL` to a disposable database with migrations 006 and 007 applied.
- These tests skip when the test URL is absent. Ordinary CI does not establish live Neon connectivity.
- High-frequency collection can generate substantial writes. Configure a small, intentional set of collector jobs, monitor database storage/compute, and add a retention policy before enabling broad multi-symbol collection. No automatic pruning is claimed here.

## Liquidation event persistence

- `LiquidationStore` now supports PostgreSQL via `DATABASE_URL`, with SQLite fallback for local development.
- Apply `migrations/008_liquidation_events.sql` before using PostgreSQL-backed liquidation collection.
- The opt-in integration test is `tests/test_liquidation_postgres_integration.py`; set `TEST_DATABASE_URL` to a disposable migrated database.
- The test is skipped without `TEST_DATABASE_URL`; ordinary CI does not establish live Neon connectivity.
- EVM ERC-20 transfer logs and index-range coverage remain SQLite-backed; their multiple query/aggregation methods require a separate complete migration and validation.

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
