# Hourly Market Scan (GitHub Actions + Neon)

## Scope

The scheduled job scans all eligible Binance Spot, USDⓈ-M Futures, and COIN-M Futures symbols using the repository's existing scanner services. It does not place orders and does not require Binance API credentials. The scan payload, source timestamps, coverage counters, and per-market status are stored in one PostgreSQL JSONB snapshot per run.

## Schedule

GitHub Actions runs at minute 17 of every hour in the `Asia/Dhaka` timezone. A manual `workflow_dispatch` trigger is also available. GitHub may delay scheduled runs during high load; this is an hourly best-effort research refresh, not a real-time SLA.

## Required account setup

1. Create a Neon PostgreSQL project: https://neon.com/
2. Copy the pooled or direct PostgreSQL connection string from the Neon dashboard. Keep it private.
3. In GitHub, open this repository's **Settings → Secrets and variables → Actions**.
4. Create a repository secret named `DATABASE_URL` and paste the Neon connection string as its value.
5. Open **Actions → Hourly Spot and Futures Market Scan → Run workflow** to perform the first manual run.

Do not put the database URL in source code, workflow YAML, README, or committed `.env` files.

## Storage and retention

The workflow creates `market_scan_runs` automatically. Each row stores one complete run envelope and all three market scan responses in JSONB. The default retention is 14 days; older rows are deleted after a successful insert. Change `MARKET_SCAN_RETENTION_DAYS` in the workflow only after checking Neon storage usage.

## Current boundaries

- This is a scheduled market-universe scan and snapshot pipeline, not a 24/7 FastAPI host.
- It stores the existing Stage-1 scanner outputs; it does not claim that every advanced Master Prompt research phase has run.
- The scanners explicitly report metrics they did not collect and may return `INCOMPLETE`; those fields must not be interpreted as verified.
- The existing historical analysis stores in the FastAPI application are SQLite-based and are not migrated by this workflow. This snapshot table is the first PostgreSQL-backed persistence layer.
- One workflow run is serialized to prevent overlapping scheduled/manual executions.
- A future public API can read the shared snapshots rather than rescanning Binance for every user. Before public launch, add authentication, rate limits, API read endpoints, observability, load tests, and a paid capacity plan.
