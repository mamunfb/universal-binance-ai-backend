# Manual Collection Lease Coordination Design

## Scope

This design covers operator-triggered HTTP collection endpoints that write market history also written by scheduled collectors. It does not enable collectors, change deployment configuration, or authorize multi-instance production operation.

## Verified current behavior on `feat/aggregate-trade-collector-lease-lifecycle`

- `HistoricalKlineCollector` uses the stable PostgreSQL lease name `historical-kline-collector`, renews it, and passes its current lease to `HistoricalKlineStore.save_klines`.
- `HistoricalKlineStore.save_klines` calls `PostgresCollectorLease.lock_if_owned` in the same PostgreSQL transaction as its upsert when a lease is supplied.
- `POST /api/v1/history/klines/{market}/{symbol}/collect` now acquires and passes the shared `historical-kline-collector` lease before its fenced store write.
- Manual funding-rate and open-interest collection endpoints now acquire and pass the shared `derivatives-history-collector` lease before their fenced store writes.
- `DerivativesHistoryCollector` uses one stable `derivatives-history-collector` lease and passes it to the funding-rate and open-interest store writes.
- `FundingRateStore.save` and `OpenInterestStore.save` accept optional leases and fence PostgreSQL writes in the same transaction.

- `DerivativesRatioStore.save` accepts an optional lease and validates ownership with `lock_if_owned` in the same PostgreSQL transaction as its upsert; the manual ratio endpoint acquires a dedicated per-series lease.
- `main.py` initializes `EVMTransferStore` with `settings.database_url`, so the service uses PostgreSQL when configured and SQLite otherwise. `save_chunk` accepts an optional lease and validates it with `lock_if_owned` in the same transaction as transfer inserts and range-coverage writes.
- The EVM indexer now acquires a per-chain/per-contract lease (`evm-transfer-indexer:{chain_id}:{contract}`) in PostgreSQL mode, renews it after each RPC chunk and before the protected write, passes it into `save_chunk`, and releases it in `finally`. Acquisition cancellation attempts to release a lease acquired during shutdown. SQLite mode remains single-process and does not use a distributed lease. Migration `012_manual_history_and_evm_transfer.sql` creates the PostgreSQL derivatives-ratio, EVM transfer, and EVM range-coverage tables. A `TEST_DATABASE_URL` integration test now exercises both fenced stores against the migrated PostgreSQL schema.

## Implemented first step: shared global lease for manual klines

Implemented on this branch in commit `049c65c`, with endpoint regression tests in `207bab4`:

- The manual historical-kline endpoint now acquires the same `historical-kline-collector` lease as the scheduled collector.
- A held lease returns HTTP 409 before the Binance provider is called.
- The lease is renewed after the provider request and immediately before the store write.
- The current lease is passed to `HistoricalKlineStore.save_klines`, which performs same-transaction fencing.
- The lease is released in `finally` after success, empty results, or provider/store errors; acquisition cancellation also attempts to reap a lease acquired during shutdown.
- Added mocked tests for success/pass-through/release, busy lease/no provider call, and provider failure/release.

This step is not yet PostgreSQL concurrency verified. CI runs #1562, #1563, and #1564 report failure, but GitHub's job-log endpoint currently returns 404 and exposes no step details. Do not infer the failure cause or treat the tests as passing.

## Implemented behavior: shared global lease

Use the exact scheduled collector lease name for the matching manual endpoint:

- Historical klines: `historical-kline-collector`
- Derivatives history: `derivatives-history-collector`

For a manual request in PostgreSQL mode:

1. Construct `PostgresCollectorLease` with the same database URL, lease name, and configured TTL used by the scheduled collector.
2. Attempt `acquire()` before making the Binance provider request.
3. If acquisition returns `None`, return HTTP 409 with a stable, non-sensitive conflict code. Do not call Binance and do not write.
4. Fetch provider data only after acquiring the lease. Never hold a database transaction or row lock across the network request.
5. Before writing, pass the acquired lease to the store method. The store must call `lock_if_owned` in the same PostgreSQL transaction as the write.
6. Release the lease in a `finally` block, including provider errors, empty results, validation errors, and request cancellation. Do not release if ownership has been lost.
7. Keep SQLite/local mode behavior unchanged and explicitly single-process-only; do not construct a PostgreSQL lease when no PostgreSQL URL is configured.

This intentionally serializes manual requests with the corresponding scheduled collector, even when the requested symbol differs. That is conservative but uses the already-established ownership boundary and avoids a partial migration to per-series leases. A later per-series design would require changing scheduled acquisition and all manual paths together.

## Implemented second step: manual derivatives endpoints

Implemented in commit `a4b3ed1`, with regression coverage in `cfdfdff`:

- Manual funding-rate and open-interest endpoints acquire the exact `derivatives-history-collector` lease used by the scheduled collector.
- A held lease returns HTTP 409 before calling Binance.
- After fetching, each endpoint renews ownership and passes the renewed lease into its store write, which performs same-transaction fencing.
- Both endpoints release the lease in `finally`; empty provider responses also release it.
- Added tests for manual funding success/lease pass-through/release and open-interest conflict/no-provider-call.

These are mocked endpoint tests only. PostgreSQL concurrency integration and CI success remain outstanding.

## Implemented third step: manual derivatives-ratio endpoint

Implemented in commit `ce312c3`, with endpoint tests in `2295832`:

- The manual ratio endpoint acquires a dedicated per-series lease named `derivatives-ratio:{ratio_type}:{symbol}:{period}`.
- Competing requests for the same ratio series return HTTP 409 before upstream work; different series can proceed independently.
- The lease is renewed before persistence and passed to `DerivativesRatioStore.save`.
- The store validates ownership with `lock_if_owned` in the same PostgreSQL transaction as its upsert; stale writes are rejected.
- SQLite mode remains unchanged and does not construct a PostgreSQL lease.

Mocked endpoint coverage is added. A PostgreSQL two-session fencing test and successful CI are still required.

## Implemented fourth step: EVM transfer indexer lease lifecycle

Implemented in the EVM store/indexer changes and migration `012_manual_history_and_evm_transfer.sql`:

- PostgreSQL-backed EVM transfer chunk writes call `lock_if_owned` in the same transaction as transfer rows and indexed-range coverage.
- The indexer acquires `evm-transfer-indexer:{chain_id}:{contract}` before scanning, renews after each RPC chunk and immediately before persistence, and passes the lease to `save_chunk`.
- Lease acquisition cancellation attempts to release a lease acquired during shutdown; the indexer releases its lease in `finally`.
- A competing indexer receives HTTP 409. SQLite mode remains single-process and does not use a distributed lease.
- Added unit coverage for acquisition/renewal/pass-through/release, held-lease rejection, SQLite lease rejection, and API conflict mapping.
- Added PostgreSQL integration tests for ratio and EVM writes, including stale-lease rejection. These tests run only when `TEST_DATABASE_URL` is configured and the migration workflow has applied the schema.

The CI job currently reports failure, but GitHub's job-step and log endpoints are returning no step details / 404. These tests and migrations must not be considered verified until a passing workflow run is available.

## Manual endpoint cancellation and blocking-worker lifecycle

The manual historical-kline, funding-rate, open-interest, and derivatives-ratio endpoints now route blocking PostgreSQL lease acquisition, renewal, protected writes, and release through a shared thread-worker drain helper. If a request is cancelled while a database worker is active, the endpoint waits for the thread to finish before propagating cancellation. Acquisition cleanup attempts to release any lease acquired during shutdown; renewal completion updates the local lease snapshot before cleanup; and protected writes are drained before the `finally` release path proceeds. Five regression tests cover repeated cancellation during a blocking worker, derivatives lease acquisition with lease reaping, lease release, latest-lease release after a cancelled renewal, and draining a kline write before releasing the renewed lease.

These changes are not yet test-verified. The latest inspected GitHub Actions run is #1652 (head `72975679492b77d05c15cc258c7ca7b9295715ba`); its job failed with `runner_id=0`, an empty runner name, and no steps. The job-log endpoint has not provided usable logs. Additional PostgreSQL integration tests now cover stale-lease rejection for manual funding-rate, open-interest, and historical-kline writes, alongside the existing derivatives-ratio and EVM transfer checks. Do not treat these tests or the full workflow as passing until a runner executes the test suite successfully.

## Required regression tests

- Scheduled collector owns the lease: manual endpoint returns 409, provider is not called, and no store write occurs.
- Manual request acquires the lease: provider is called once, store receives the exact acquired lease, and release occurs once.
- Provider raises: lease is released and no write occurs.
- Provider returns no rows: lease is released and no write occurs.
- Store rejects a stale lease: endpoint does not report success; ownership is not incorrectly released as if still current.
- Concurrent manual requests: only one obtains the lease; the other returns 409 without upstream work.
- PostgreSQL integration: a two-session test proves the fenced write and lease takeover ordering; mocked manager tests alone are not sufficient evidence of database fencing.

## Remaining write-path audit

| Write path | Store fencing | Runtime passes lease | Assessment |
|---|---|---|---|
| Scheduled historical klines | Yes | Yes | Fenced |
| Manual historical klines | Yes, optional | Yes (shared global lease) | Implemented; CI/log verification pending |
| Scheduled funding rates | Yes | Yes | Fenced |
| Manual funding rates | Yes, optional | Yes (shared derivatives lease) | Implemented; CI/integration pending |
| Scheduled open interest | Yes | Yes | Fenced |
| Manual open interest | Yes, optional | Yes (shared derivatives lease) | Implemented; CI/integration pending |
| Manual derivatives ratios | Yes, optional | Yes (per-series lease) | Implemented; PostgreSQL integration test added, CI result pending |
| EVM transfer chunk indexing | Yes | Yes (per-chain/per-contract lease) | Implemented; PostgreSQL integration test added, CI result pending |
| Aggregate trade stream | Yes | Yes | Fenced |
| Order-book stream | Yes | Yes | Fenced |
| Liquidation stream | Yes | Yes | Fenced |

## Safety gates

- Collector enablement flags remain disabled.
- No Render, Cloudflare, or production configuration changes.
- No PR merge or deployment.
- Do not claim multi-instance readiness until the manual endpoints, EVM transfer indexer, and PostgreSQL concurrency tests are verified by passing CI and database-backed tests.
