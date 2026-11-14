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

- `DerivativesRatioStore.save` currently has no lease parameter or same-transaction fencing check; its manual collection endpoint writes directly.
- `main.py` initializes `EVMTransferStore` with `settings.database_url`, so the service uses PostgreSQL when configured and SQLite otherwise. `save_chunk` now accepts an optional lease and validates it with `lock_if_owned` in the same transaction as transfer inserts and range-coverage writes. The indexer does not yet acquire or pass a lease; runtime coordination remains outstanding.

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
| Manual derivatives ratios | Yes, optional | Yes (per-series lease) | Implemented; CI/integration pending |
| EVM transfer chunk indexing | Yes, optional | No | Store fencing added; indexer lease lifecycle still required |
| Aggregate trade stream | Yes | Yes | Fenced |
| Order-book stream | Yes | Yes | Fenced |
| Liquidation stream | Yes | Yes | Fenced |

## Safety gates

- Collector enablement flags remain disabled.
- No Render, Cloudflare, or production configuration changes.
- No PR merge or deployment.
- Do not claim multi-instance readiness until the manual endpoints, EVM transfer storage architecture, and PostgreSQL concurrency tests are complete.
