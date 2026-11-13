# Collector Ownership and Multi-Instance Safety

## Audit status

This document records the current collector deployment boundary. It does not enable collectors, change deployment settings, or claim distributed ownership is implemented.

### Current behavior

The application starts each enabled collector from the FastAPI lifespan in every backend process:

- Binance USD-M liquidation force-order stream
- Order-book depth streams, one task per allow-listed market/symbol job
- Aggregate-trade streams, one task per allow-listed market/symbol job
- Historical-kline polling collector
- Derivatives funding/open-interest polling collector

The collectors use process-local asyncio tasks. There is no shared PostgreSQL owner election, lease, advisory lock, or fencing token in the current implementation. Consequently, if two Render instances start with the same collector flags and job configuration, both can start the same subscriptions and polling jobs.

PostgreSQL persistence alone does not provide single-owner execution.

### Persistence and duplicate handling

| Collector | PostgreSQL duplicate protection | Assessment |
|---|---|---|
| Order book | Unique key on `(market, symbol, update_id)`; inserts use `ON CONFLICT DO NOTHING` | Repeated samples for the same update are suppressed |
| Aggregate trades | Unique key on `(market, symbol, trade_id)`; inserts use `ON CONFLICT DO NOTHING` | Replayed trade IDs are suppressed |
| Liquidations | No natural-event unique constraint; inserts do not use conflict handling | Duplicate subscriptions can create duplicate history rows |
| Historical klines | Review the per-store upsert/unique-key behavior before multi-instance enablement | Do not infer single-owner behavior from shared storage |
| Derivatives polling | Review each history store's uniqueness and polling overlap behavior before multi-instance enablement | Concurrent pollers can duplicate upstream work even where storage is idempotent |

The Binance USD-M force-order stream is a snapshot stream, not a complete liquidation tape: Binance may publish at most the latest liquidation order per symbol within a 1,000 ms interval, and an empty interval produces no event. Duplicate persistence protection must not be presented as a way to recover events that the upstream stream does not publish.

### Current lifecycle protections

- Startup is inside a `try/finally` region so a later collector startup exception still enters cleanup.
- Shutdown attempts each instantiated collector even if another collector's stop method raises; failures are logged.
- A regression test simulates a startup failure and a separate stop failure, then verifies that the liquidation collector's cleanup is still attempted.
- Backend CI at commit `263c62909ea910c263f4b346eb8611a3c58c4e8d` passed 618 tests with 2 warnings.
- Neon staging PostgreSQL integration at the same commit passed, including the read-only schema verification and real PostgreSQL integration tests.

These protections address process-local startup and cleanup. They do not coordinate multiple application instances.

## Required design before multi-instance collector operation

A production-grade owner mechanism should be implemented and tested before enabling collectors on more than one backend instance.

The design must cover:

1. **One owner across all collector groups** or an explicitly partitioned owner key per market/symbol job.
2. **Atomic acquisition** using PostgreSQL coordination, not a process-local flag.
3. **Renewal/health checks** and a bounded failure-detection interval.
4. **Crash recovery** so a standby can take ownership after the previous owner disappears.
5. **Fencing** so a former owner that has lost ownership cannot continue writing after a new owner takes over.
6. **Graceful shutdown** that stops streams and polling tasks before releasing ownership.
7. **Observability** exposing owner identity, acquisition state, last renewal, and failure reason without exposing secrets.
8. **Concurrency tests** using two independent database sessions, including owner crash, connection loss, stale-owner takeover, and shutdown failure.
9. **Idempotent persistence** for every collector, especially liquidation events, with a migration strategy that safely handles existing rows without destructive cleanup.

A plain advisory lock can prevent two healthy sessions from owning the same key, but by itself it does not fence a process whose network connection has been lost while its local stream tasks continue. A lease without fencing has the same stale-owner risk. The implementation must address both ownership and stale-writer behavior.

## Operational restriction until this is implemented

- Keep all collector flags disabled on Render staging and production.
- Do not use multiple Render instances for collector execution.
- Do not assume Neon shared storage prevents duplicate subscriptions.
- Do not introduce retention deletion until archive, restore, and integrity verification are complete.
- Treat the current stream/polling collectors as single-process-only.

This document is an audit record and implementation gate, not a claim that distributed collector ownership is already available.
