# Manual Collection Lease Coordination Design

## Scope

This design covers operator-triggered HTTP collection endpoints that write market history also written by scheduled collectors. It does not enable collectors, change deployment configuration, or authorize multi-instance production operation.

## Verified current behavior on `feat/aggregate-trade-collector-lease-lifecycle`

- `HistoricalKlineCollector` uses the stable PostgreSQL lease name `historical-kline-collector`, renews it, and passes its current lease to `HistoricalKlineStore.save_klines`.
- `HistoricalKlineStore.save_klines` calls `PostgresCollectorLease.lock_if_owned` in the same PostgreSQL transaction as its upsert when a lease is supplied.
- `POST /api/v1/history/klines/{market}/{symbol}/collect` currently fetches from Binance and calls `save_klines` without a lease.
- `DerivativesHistoryCollector` uses one stable `derivatives-history-collector` lease and passes it to the funding-rate and open-interest store writes.
- `FundingRateStore.save` and `OpenInterestStore.save` accept optional leases and fence PostgreSQL writes in the same transaction.
- The manual funding-rate and open-interest collection endpoints currently omit a lease.
- `DerivativesRatioStore.save` currently has no lease parameter or same-transaction fencing check; its manual collection endpoint writes directly.
- `EVMTransferStore.save_chunk` currently has no lease parameter. EVM transfer indexing is a separate workflow and is outside this manual market-history lease change.

## Recommended first implementation: shared global lease

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
| Manual historical klines | Yes, optional | No | Must coordinate |
| Scheduled funding rates | Yes | Yes | Fenced |
| Manual funding rates | Yes, optional | No | Must coordinate |
| Scheduled open interest | Yes | Yes | Fenced |
| Manual open interest | Yes, optional | No | Must coordinate |
| Manual derivatives ratios | No | No | Separate lease/fencing work required |
| EVM transfer chunk indexing | No | No | Separate workflow audit required |
| Aggregate trade stream | Yes | Yes | Fenced |
| Order-book stream | Yes | Yes | Fenced |
| Liquidation stream | Yes | Yes | Fenced |

## Safety gates

- Collector enablement flags remain disabled.
- No Render, Cloudflare, or production configuration changes.
- No PR merge or deployment.
- Do not claim multi-instance readiness until the manual endpoints, derivatives-ratio path, EVM transfer workflow, and PostgreSQL concurrency tests are complete.
