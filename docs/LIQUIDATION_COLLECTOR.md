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

This is an opt-in background task and is disabled by default. Do not use a scale-to-zero or short-lived serverless runtime; the process must remain alive. Run only one collector-owning process for this all-market stream to avoid duplicate subscriptions and stored snapshots, regardless of whether PostgreSQL or SQLite is used.

## Endpoints

- `GET /api/v1/analysis/futures/liquidations/status`
- `GET /api/v1/analysis/futures/liquidations/recent?symbol=BTCUSDT&limit=100`

The notional field is calculated as average price × cumulative filled quantity from the received snapshot. It is an approximate snapshot-derived value, not a verified total liquidation amount for the market.

## Operational caveats

- The collector records only messages received while it is connected and running.
- Disconnects create gaps; reconnect count and last error are exposed in status.
- No historical backfill is provided.
- No heatmap or liquidation price clusters are claimed.
- PostgreSQL/Neon is supported through DATABASE_URL, but it does not coordinate collector ownership. For multi-instance deployments, use a single elected stream consumer or a durable message queue; simply sharing one database URL across replicas can still duplicate stream capture.
