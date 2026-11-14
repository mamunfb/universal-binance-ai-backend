# Collector Ownership and Multi-Instance Safety

## Audit status

This document records the current collector deployment boundary. Migration 011 and the PostgreSQL lease primitive are groundwork only. They do not enable collectors, change deployment settings, or claim distributed ownership is fully integrated.

### Current execution model

The FastAPI lifespan starts enabled collectors inside each backend process:

- Binance USD-M liquidation force-order stream
- Order-book depth streams
- Aggregate-trade streams
- Historical-kline polling
- Derivatives funding/open-interest polling

These collectors use process-local asyncio tasks. Until every collector's data writes are fenced, two backend instances with the same collector flags can still run duplicate upstream subscriptions or polling jobs. Shared PostgreSQL persistence does not provide single-owner execution.

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

## PostgreSQL lease primitive (implemented, not wired into collectors)

Migration 011 adds public.collector_leases with a monotonic fencing token per named lease. PostgresCollectorLease provides:

- Atomic acquisition that returns no lease while another live owner holds it.
- Renewal only by the matching owner and fencing token, while the lease is still live.
- Release by expiring the row rather than deleting it, preserving token history.
- lock_if_owned(connection, lease), which uses SELECT ... FOR SHARE and must run in the same PostgreSQL transaction as the protected data write. A takeover update cannot advance the token while that transaction holds the row lock.

The primitive alone does not fence existing collector writes. As a first persistence-layer step, `HistoricalKlineStore.save_klines` now accepts an optional lease and, when supplied for PostgreSQL storage, validates it with `lock_if_owned` on the same transaction/connection as the candle upsert. A stale lease raises `CollectorLeaseLostError` before any candle is written; SQLite storage rejects a supplied lease. The existing `HistoricalKlineCollector` does not yet acquire, renew, or pass a lease, so this protection is not active in its runtime path. A future integration must wire lease acquisition/heartbeat/task shutdown and update every remaining collector persistence path. Network calls must remain outside protected write transactions.

The PostgreSQL integration tests cover simultaneous acquisition by two independent owners, expired-lease takeover and token increment, stale-owner renewal/release/write-guard rejection, renewal, monotonic token preservation across release, and a two-session check that an active fenced write transaction blocks an expired lease takeover until commit. These tests use TEST_DATABASE_URL; a skipped local run is not evidence of PostgreSQL verification.

## Required integration before multi-instance collector operation

1. Define explicit lease scopes (one global owner or deterministic per-job partitions) and stable owner identity per process.
2. Add heartbeat/renewal with a bounded failure-detection interval; stop all associated tasks immediately on renewal loss.
3. Pass the lease token to every collector store write and call lock_if_owned in the same transaction as that write.
4. Ensure all writes in a batch are protected; do not check a lease in one connection and write in another.
5. Add two-connection tests for simultaneous acquisition, expiry takeover, stale-owner writes, renewal loss, and shutdown failure.
6. Expose owner identity, lease state, token, last renewal, and failure reason without exposing secrets.
7. Verify graceful shutdown stops streams and polling before releasing leases.

## Operational restriction until integration is complete

- Keep all collector flags disabled on Render staging and production.
- Do not use multiple Render instances for collector execution.
- Do not assume Neon shared storage prevents duplicate subscriptions or upstream polling.
- Do not introduce retention deletion until archive, restore, and integrity verification are complete.
- Treat the current collectors as single-process-only. Migration 011 and the lease class are groundwork, not authorization to enable multi-instance collectors.
