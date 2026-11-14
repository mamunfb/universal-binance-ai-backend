# Collector Ownership and Multi-Instance Safety

## Audit status

This document records the current collector deployment boundary. It does not enable collectors, change deployment settings, or claim distributed ownership is implemented.

### Execution model

The FastAPI lifespan starts enabled collectors inside each backend process:

- Binance USD-M liquidation force-order stream
- Order-book depth streams
- Aggregate-trade streams
- Historical-kline polling
- Derivatives funding/open-interest polling

These collectors use process-local asyncio tasks. There is no shared PostgreSQL owner election, lease, advisory lock, or fencing token. If two backend instances start with the same collector flags and jobs, both can run the same subscriptions or polling jobs. Shared PostgreSQL persistence does not provide single-owner execution.

### Verified persistence and duplicate handling

| Collector | Database uniqueness / write behavior | What it protects |
|---|---|---|
| Order book | Unique `(market, symbol, update_id)`; insert uses conflict-ignore | Suppresses repeated samples with the same update ID |
| Aggregate trades | Unique `(market, symbol, trade_id)`; insert uses conflict-ignore | Suppresses replayed aggregate-trade IDs |
| Liquidations | SHA-256 fingerprint over canonical raw payload and normalized event fields; unique `event_fingerprint` index in SQLite and PostgreSQL; insert uses conflict-ignore | Suppresses exact repeated payloads only; distinct payloads remain distinct rows |
| Historical klines | Primary key `(market, symbol, interval, open_time_ms)`; upsert updates an existing candle | Makes repeated candle collection idempotent and allows the still-forming candle to be refreshed |
| Funding rates | Primary key `(market, symbol, funding_time_ms)`; upsert | Makes repeated funding-event collection idempotent |
| Open interest | Primary key `(market, symbol, period, timestamp_ms)`; upsert | Makes repeated open-interest collection idempotent |

These constraints protect persistence from some duplicate writes; they do not prevent duplicate upstream requests, subscriptions, CPU/network use, or two collectors racing to collect the same job.

The liquidation fingerprint is an exact-payload deduplication mechanism, not an exchange-native event identifier. It cannot prove that semantically identical events with different payload representations will collapse into one row, nor should it merge distinct events. The Binance USD-M force-order stream is a snapshot stream rather than a complete liquidation tape; persistence deduplication cannot recover events the upstream stream does not publish.

### Lifecycle and runtime caveats

- Collector startup occurs within a protected FastAPI lifespan region, and shutdown attempts cleanup for instantiated collectors.
- Collector status and error reporting should expose exception classes rather than sensitive provider/database exception text.
- The historical and derivatives polling collectors isolate per-job failures and continue processing later jobs in the same cycle.
- These are process-local lifecycle protections only. They do not coordinate multiple backend instances.
- CI success validates the test/build workflow at the tested commit; it does not prove Render's live environment has the intended database URL, collector flags, or runtime ownership.

## Required design before multi-instance collector operation

A production-grade ownership mechanism must be implemented and tested before enabling collectors on more than one backend instance.

The design must cover:

1. **One owner across collector groups** or an explicitly partitioned owner key per market/symbol job.
2. **Atomic acquisition** using PostgreSQL coordination, not a process-local flag.
3. **Renewal and health checks** with a bounded failure-detection interval.
4. **Crash recovery** so a standby can take ownership after the previous owner disappears.
5. **Fencing** so a former owner that has lost ownership cannot continue writing after a new owner takes over.
6. **Graceful shutdown** that stops streams and polling tasks before releasing ownership.
7. **Observability** exposing owner identity, acquisition state, last renewal, and failure reason without exposing secrets.
8. **Concurrency tests** using two independent database sessions, including owner crash, connection loss, stale-owner takeover, and shutdown failure.
9. **Idempotent persistence** for every collector, with a safe migration strategy for existing rows.

A plain advisory lock can prevent two healthy sessions from owning the same key, but by itself it does not fence a process whose database connection has been lost while its local stream tasks continue. A lease without fencing has the same stale-owner risk. The implementation must address both ownership and stale-writer behavior.

## Operational restriction until this is implemented

- Keep all collector flags disabled on Render staging and production.
- Do not use multiple Render instances for collector execution.
- Do not assume Neon shared storage prevents duplicate subscriptions or upstream polling.
- Do not introduce retention deletion until archive, restore, and integrity verification are complete.
- Treat the current stream/polling collectors as single-process-only.

This document is an audit record and implementation gate, not a claim that distributed collector ownership is already available.
