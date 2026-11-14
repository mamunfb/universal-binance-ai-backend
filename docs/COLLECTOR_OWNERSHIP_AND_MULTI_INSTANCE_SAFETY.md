# Collector Ownership and Multi-Instance Safety

## Audit status

This document records the current collector deployment boundary. Migrations 011 and 012 and the PostgreSQL lease primitive are groundwork; the historical-kline collector now uses the lease lifecycle and fenced writes when backed by PostgreSQL. The manual historical-kline, funding-rate, and open-interest HTTP collection endpoints now acquire the same named PostgreSQL leases as their scheduled collectors and pass those leases into same-transaction fenced writes. Manual derivatives-ratio collection now uses a per-series PostgreSQL lease and same-transaction fenced writes. EVM transfer indexing now uses per-chain/per-contract leases and same-transaction fenced chunk writes. CI is currently failing and must be diagnosed before these changes are considered verified. No deployment settings or collector flags are enabled by this work.

### Current execution model

The FastAPI lifespan starts enabled collectors inside each backend process:

- Binance USD-M liquidation force-order stream
- Order-book depth streams
- Aggregate-trade streams
- Historical-kline polling
- Derivatives funding/open-interest polling

These collectors use process-local asyncio tasks. The historical-kline and derivatives-history polling tasks now acquire separate named PostgreSQL leases before starting, renew them while running, pass fencing tokens to each PostgreSQL history write, and exit permanently for that process if ownership is lost. Order-book and aggregate-trade stream tasks now use per-market/symbol PostgreSQL leases and fenced inserts. The liquidation stream now acquires and renews a PostgreSQL lease before connecting, fences every event insert, stops on ownership loss, and releases its lease during orderly shutdown. Shared PostgreSQL persistence does not provide single-owner execution by itself.

### Verified persistence and duplicate handling

| Collector | Database uniqueness / write behavior | What it protects |
|---|---|---|
| Order book | Unique (market, symbol, update_id); insert uses conflict-ignore | Suppresses repeated samples with the same update ID |
| Aggregate trades | Unique (market, symbol, trade_id); insert uses conflict-ignore | Suppresses replayed aggregate-trade IDs |
| Liquidations | SHA-256 fingerprint over canonical raw payload and normalized event fields; unique event_fingerprint index in SQLite and PostgreSQL; insert uses conflict-ignore | Suppresses exact repeated payloads only; distinct payloads remain distinct |
| Historical klines | Primary key (market, symbol, interval, open_time_ms); upsert updates an existing candle | Makes repeated candle collection idempotent and allows the still-forming candle to be refreshed |
| Funding rates | Primary key (market, symbol, funding_time_ms); upsert | Makes repeated funding-event collection idempotent |
| Open interest | Primary key (market, symbol, period, timestamp_ms); upsert | Makes repeated open-interest collection idempotent |

These constraints protect persistence from some duplicate writes; they do not prevent duplicate upstream requests, subscriptions, CPU/network use, or two collectors racing to collect the same job.

The liquidation fingerprint is exact-payload deduplication, not an exchange-native event identifier. It cannot prove that semantically identical events with different payload representations will collapse into one row. Binance USD-M force-order messages are snapshots, not a complete liquidation tape; persistence deduplication cannot recover events the upstream stream does not publish.

## PostgreSQL lease primitive and historical-kline integration (partial)

Migration 011 adds public.collector_leases with a monotonic fencing token per named lease. PostgresCollectorLease provides:

- Atomic acquisition that returns no lease while another live owner holds it.
- Renewal only by the matching owner and fencing token, while the lease is still live.
- Release by expiring the row rather than deleting it, preserving token history.
- lock_if_owned(connection, lease), which uses SELECT ... FOR SHARE and must run in the same PostgreSQL transaction as the protected data write. A takeover update cannot advance the token while that transaction holds the row lock.

`HistoricalKlineStore.save_klines` accepts an optional lease and validates it with `lock_if_owned` on the same transaction/connection as the candle upsert. A stale lease raises `CollectorLeaseLostError` before any candle is written; SQLite storage rejects a supplied lease. When a PostgreSQL historical-kline database URL is configured, `HistoricalKlineCollector` now acquires the stable `historical-kline-collector` lease before polling, renews it at roughly one-third of the configured TTL, passes the current lease to each candle write, and releases it during orderly shutdown. If acquisition is unavailable, it does not collect. If renewal is lost, it stops and does not automatically reacquire in that process. The default TTL is 30 seconds and can be changed with `HISTORICAL_COLLECTOR_LEASE_TTL_SECONDS`. When only SQLite is configured, no distributed lease is used and the collector remains single-process-only. Network calls remain outside protected write transactions.

The scheduled and manual historical-kline paths now share the same named lease. The manual endpoint acquires before the provider request, renews before its write, and passes the lease to the same-transaction fencing guard. This endpoint-level integration has mocked regression tests but still requires successful CI and PostgreSQL concurrency verification.

FundingRateStore.save and OpenInterestStore.save also accept optional leases and validate ownership on the same PostgreSQL transaction as their upserts. DerivativesHistoryCollector acquires the stable derivatives-history-collector lease before polling, renews at roughly one-third of the configured TTL, fences both funding-rate and open-interest writes, and does not collect while another live owner holds the lease. A renewal failure or rejected fenced write stops the collector without automatic reacquisition. The default TTL is 30 seconds and is configured with DERIVATIVES_COLLECTOR_LEASE_TTL_SECONDS. SQLite mode remains single-process-only. Direct run_once() calls are rejected when PostgreSQL lease mode is configured but no current lease is held.

This integration covers scheduled historical-kline and derivatives-history, their corresponding manual HTTP endpoints, the live liquidation stream, order-book streams, and aggregate-trade streams. Manual derivatives-ratio and EVM transfer indexer lease lifecycles are implemented but require CI and PostgreSQL integration verification. Do not treat this as full multi-instance readiness.

The persistence layer supports optional fencing for `OrderBookHistoryStore.insert`, `AggregateTradeStore.insert`, and `LiquidationStore.insert`: each validates the lease in the same PostgreSQL transaction as its insert. The liquidation runtime now acquires the stable `liquidation-stream-collector` lease, renews it at roughly one-third of the configured TTL, passes the current lease to every insert, and treats a rejected write or failed renewal as terminal for that process (no automatic reacquisition). The default TTL is 30 seconds and is configured with `LIQUIDATION_COLLECTOR_LEASE_TTL_SECONDS`. If another live owner holds the lease, the stream does not connect. Order-book runtime tasks acquire the stable `order-book:{market}:{symbol}` lease before connecting, renew at roughly one-third of the configured TTL, pass the current lease to every insert, and stop permanently on renewal loss or a fenced write rejection. The default TTL is 30 seconds and is configured with `ORDER_BOOK_COLLECTOR_LEASE_TTL_SECONDS`. If another live owner holds a job lease, that stream does not connect. Aggregate-trade runtime tasks acquire the stable `aggregate-trade:{market}:{symbol}` lease before connecting, renew at roughly one-third of the configured TTL, pass the current lease to every insert, and stop permanently on renewal loss or a fenced write rejection. The default TTL is 30 seconds and is configured with `AGGREGATE_TRADE_COLLECTOR_LEASE_TTL_SECONDS`. If another live owner holds a job lease, that stream does not connect. Both SQLite-backed stream collectors remain single-process-only. SQLite-backed inserts reject a supplied lease.

The PostgreSQL integration tests cover simultaneous acquisition by two independent owners, expired-lease takeover and token increment, stale-owner renewal/release/write-guard rejection, renewal, monotonic token preservation across release, and a two-session check that an active fenced write transaction blocks an expired lease takeover until commit. These tests use TEST_DATABASE_URL; a skipped local run is not evidence of PostgreSQL verification.

## Required integration before multi-instance collector operation

1. Audit every remaining collector persistence path and confirm it calls lock_if_owned in the same transaction as its write; cover all batch writes.
2. Complete EVM transfer PostgreSQL concurrency verification and confirm cancellation/partial-range behavior in CI. The manual kline, funding-rate, and open-interest endpoints share their scheduled collectors' leases; manual derivatives ratios use per-series leases.
3. Add two-connection tests for any remaining unfenced write path and shutdown behavior.
4. Expose owner identity, lease state, token, last renewal, and failure reason without exposing secrets.
5. Verify graceful shutdown stops streams and polling before releasing leases.

## Operational restriction until integration is complete

- Keep all collector flags disabled on Render staging and production.
- Do not use multiple Render instances for collector execution.
- Do not assume Neon shared storage prevents duplicate subscriptions or upstream polling.
- Do not introduce retention deletion until archive, restore, and integrity verification are complete.
- Do not treat the platform as multi-instance-ready. Historical-kline, derivatives-history, liquidation, order-book, aggregate-trade, manual derivatives-ratio, and EVM transfer indexer paths now have PostgreSQL lease fencing. CI diagnosis and successful PostgreSQL concurrency verification remain outstanding. Migrations 011/012 and the lease class are not authorization to enable multi-instance collectors.
