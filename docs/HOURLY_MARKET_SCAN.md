# Scheduled Market Scan (GitHub Actions + Neon)

## Scope

The scheduled job scans all eligible Binance Spot, USDⓈ-M Futures, and COIN-M Futures symbols using the repository's existing scanner services. It does not place orders and does not require Binance API credentials. The scan payload, source timestamps, coverage counters, and per-market status are stored in one PostgreSQL JSONB snapshot per run.

This is the initial market-universe collection layer. It is not the complete AI research engine and does not claim that every phase in the canonical Spot and Futures Master Prompts has executed.

## Schedule

On the `fix/binance-public-market-data-endpoints` branch, the workflow is named `3-Hour Spot and Futures Market Scan` and its cron schedule is `0 */3 * * *` in the `Asia/Dhaka` timezone. A manual `workflow_dispatch` trigger is also available. The `main` branch has a separate workflow definition with a 15-minute schedule; do not assume the two branches have identical schedules. GitHub scheduled jobs can be delayed or dropped during periods of high load. This is periodic research refresh, not a real-time SLA or an always-on process.

## Required account setup

1. Create a Neon PostgreSQL project: https://neon.com/
2. Copy the pooled or direct PostgreSQL connection string from the Neon dashboard. Keep it private.
3. In GitHub, open this repository's **Settings → Secrets and variables → Actions**.
4. Create a repository secret named `DATABASE_URL` and paste the Neon connection string as its value.
5. On the feature branch, open **Actions → 3-Hour Spot and Futures Market Scan → Run workflow** to perform a manual run. The workflow also requires the repository Actions secret `DATABASE_URL`.

Do not put the database URL in source code, workflow YAML, README, or committed `.env` files. Do not paste the connection string into chat.

## Storage and retention

The workflow creates `market_scan_runs` automatically. Each row stores one complete run envelope and all three market scan responses in JSONB. This bootstrap collector deliberately does not delete historical rows.

The intended long-term architecture is Neon for queryable recent/structured history and Cloudflare R2 for long-term raw archives. Before any retention deletion is introduced, implement and test R2 export, archive integrity verification, restore support, and an archive-before-delete process. Until then, monitor Neon storage usage; the database can grow and the free-tier capacity is not guaranteed to be sufficient for indefinite full snapshots.

## Current boundaries

- This is a scheduled market-universe scan, not a 24/7 FastAPI host.
- It stores the existing Stage-1 scanner outputs; it does not claim that every advanced Master Prompt research phase has run.
- The scanners explicitly report metrics they did not collect and may return `INCOMPLETE`; those fields must not be interpreted as verified. The stored overall research status can therefore remain `INCOMPLETE` even when the collection job succeeds. GitHub Actions exits successfully when all three collectors complete and the database write succeeds; it exits unsuccessfully for collector or persistence failures.
- The workflow's `market_scan_runs` JSONB snapshots are separate from the FastAPI collectors' structured history tables. The backend's PostgreSQL-capable stores use `DATABASE_URL` when configured and otherwise use their SQLite fallback paths. This scheduled scanner does not populate historical kline, funding-rate, open-interest, aggregate-trade, order-book, liquidation, or EVM transfer tables.
- One workflow run is serialized to prevent overlapping scheduled/manual executions.
- A future public API can read shared snapshots rather than rescanning Binance for every user. Before public launch, add authentication, rate limits, API read endpoints, observability, load tests, and a capacity plan.
