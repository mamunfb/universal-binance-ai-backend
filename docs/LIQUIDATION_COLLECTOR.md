# Liquidation Stream Collector

## Source and limitations

The collector subscribes to Binance USDⓈ-M's public all-market force-order stream:

`wss://fstream.binance.com/market/ws/!forceOrder@arr`

Binance documents this as an all-market liquidation **snapshot** stream. For each symbol, at most the latest liquidation order within a 1000 ms interval is pushed; no message is sent for an interval with no liquidation. Therefore this feed is not a complete liquidation tape, not a complete count of all forced orders, and not a historical archive.

Official reference: https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams/All-Market-Liquidation-Order-Streams

## Enable

Set these environment variables on an always-on deployment:

```env
LIQUIDATION_COLLECTOR_ENABLED=true
# Optional SQLite fallback path; DATABASE_URL selects PostgreSQL/Neon when configured.
LIQUIDATION_DATABASE_PATH=data/liquidations.sqlite3
```

Install requirements and run one always-on API process. The collector starts with FastAPI lifespan and reconnects with exponential backoff up to 60 seconds. When DATABASE_URL is configured, received snapshots are stored in PostgreSQL/Neon; otherwise they use the SQLite fallback at LIQUIDATION_DATABASE_PATH. The SQLite fallback requires persistent disk storage because ephemeral container filesystems lose local database files on restart/redeploy.

This is an opt-in background task and is disabled by default. Do not use a scale-to-zero or short-lived serverless runtime; the process must remain alive. Run only one collector-owning process for this all-market stream to avoid duplicate subscriptions and stored snapshots, regardless of whether PostgreSQL or SQLite is used. Shared PostgreSQL/Neon storage does not elect a single owner; multi-instance ownership and fencing are not implemented.

## Endpoints

- `GET /api/v1/analysis/futures/liquidations/status`
- `GET /api/v1/analysis/futures/liquidations/recent?symbol=BTCUSDT&limit=100`

The notional field is calculated as average price × cumulative filled quantity from the received snapshot. It is an approximate snapshot-derived value, not a verified total liquidation amount for the market.

## Operational caveats

- The collector records only messages received while it is connected and running.
- Disconnects create gaps; reconnect count and the last transport error class (not raw exception text) are exposed in status.
- Storage write failures are retried for the current event with exponential delays from 1 to 60 seconds. The stream remains connected while retrying that event, applying backpressure rather than dropping it or repeatedly reconnecting. Status reports `storage_status: DEGRADED`, the exception class only, and the cumulative storage retry count while a write is failing.
- No historical backfill is provided.
- The read-only liquidation-cluster analysis groups locally stored snapshots into approximate price buckets; it does not estimate future liquidation levels or repair missing source events. See `GET /api/v1/analysis/futures/liquidation-clusters/{symbol}`.
- Exact repeated force-order payloads are deduplicated with a SHA-256 fingerprint. PostgreSQL/Neon deployments must apply `migrations/010_liquidation_event_fingerprint.sql` before running this code. The migration adds a nullable column and unique index; it does not delete, rewrite, or retroactively deduplicate existing rows. SQLite adds the nullable column and index non-destructively when the store opens.
- PostgreSQL/Neon is supported through DATABASE_URL, but it does not coordinate collector ownership. For multi-instance deployments, use a single elected stream consumer or a durable message queue; simply sharing one database URL across replicas can still duplicate stream capture. See [Collector Ownership and Multi-Instance Safety](COLLECTOR_OWNERSHIP_AND_MULTI_INSTANCE_SAFETY.md).
