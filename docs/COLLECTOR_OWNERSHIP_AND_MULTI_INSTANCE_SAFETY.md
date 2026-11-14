# Collector Ownership and Multi-Instance Safety

## Audit status

This document records the current collector deployment boundary. Migration 011 and the PostgreSQL lease primitive are groundwork; the historical-kline collector now uses the lease lifecycle and fenced writes when backed by PostgreSQL. The other collector families are not yet lease-coordinated. No deployment settings or collector flags are enabled by this work.

### Current execution model

The FastAPI lifespan starts enabled collectors inside each backend process:

- Binance USD-M liquidation force-order stream
- Order-book depth streams
- Aggregate-trade streams
- Historical-kline polling
- Derivatives funding/open-interest polling

These collectors use process-local asyncio tasks. The historical-kline and derivatives-history polling tasks now acquire separate named PostgreSQL leases before starting, renew them while running, pass fencing tokens to each PostgreSQL history write, and exit permanently for that process if ownership is lost. Order-book, aggregate-trade, and liquidation collector families still lack this protection. Shared PostgreSQL persistence does not provide single-owner execution by itself.

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

This integration covers only scheduled historical-kline collection. The manual HTTP kline collection endpoint and the other collector families are not lease-fenced by this change; do not treat this as full multi-instance readiness.

FundingRateStore.save and OpenInterestStore.save also accept optional leases and validate ownership on the same PostgreSQL transaction as their upserts. DerivativesHistoryCollector acquires the stable derivatives-history-collector lease before polling, renews at roughly one-third of the configured TTL, fences both funding-rate and open-interest writes, and does not collect while another live owner holds the lease. A renewal failure or rejected fenced write stops the collector without automatic reacquisition. The default TTL is 30 seconds and is configured with DERIVATIVES_COLLECTOR_LEASE_TTL_SECONDS. SQLite mode remains single-process-only. Direct run_once() calls are rejected when PostgreSQL lease mode is configured but no current lease is held.

This integration covers only scheduled historical-kline and derivatives-history collection. Manual HTTP collection endpoints and order-book, aggregate-trade, and liquidation collectors are not lease-fenced; do not treat this as full multi-instance readiness.

The PostgreSQL integration tests cover simultaneous acquisition by two independent owners, expired-lease takeover and token increment, stale-owner renewal/release/write-guard rejection, renewal, monotonic token preservation across release, and a two-session check that an active fenced write transaction blocks an expired lease takeover until commit. These tests use TEST_DATABASE_URL; a skipped local run is not evidence of PostgreSQL verification.

## Required integration before multi-instance collector operation

1. Extend equivalent lease acquisition, heartbeat, loss handling, and shutdown to order-book, aggregate-trade, and liquidation collectors.
2. Fence every remaining collector persistence path by calling lock_if_owned in the same transaction as its write; cover all batch writes.
3. Decide whether manual collection endpoints need a separate lease or should remain explicitly operator-triggered and single-request.
4. Add two-connection tests for every remaining collector's stale-owner write path and shutdown behavior.
5. Expose owner identity, lease state, token, last renewal, and failure reason without exposing secrets.
6. Verify graceful shutdown stops streams and polling before releasing leases.

## Operational restriction until integration is complete

- Keep all collector flags disabled on Render staging and production.
- Do not use multiple Render instances for collector execution.
- Do not assume Neon shared storage prevents duplicate subscriptions or upstream polling.
- Do not introduce retention deletion until archive, restore, and integrity verification are complete.
- Treat the current collectors as single-process-only. Migration 011 and the lease class are groundwork, not authorization to enable multi-instance collectors.
