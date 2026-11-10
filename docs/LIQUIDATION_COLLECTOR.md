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
LIQUIDATION_DATABASE_PATH=data/liquidations.sqlite3
```

Install requirements and run one persistent API process. The collector starts with FastAPI lifespan and reconnects with exponential backoff up to 60 seconds. SQLite stores the received snapshots. Ensure the deployment provides persistent disk storage; ephemeral container filesystems lose the database on restart/redeploy.

This is an opt-in background task. It is disabled by default. Do not use a scale-to-zero or short-lived serverless runtime for collection; the process must remain alive. Run only one collector instance against a given SQLite database.

## Endpoints

- `GET /api/v1/analysis/futures/liquidations/status`
- `GET /api/v1/analysis/futures/liquidations/recent?symbol=BTCUSDT&limit=100`

The notional field is calculated as average price × cumulative filled quantity from the received snapshot. It is an approximate snapshot-derived value, not a verified total liquidation amount for the market.

## Operational caveats

- The collector records only messages received while it is connected and running.
- Disconnects create gaps; reconnect count and last error are exposed in status.
- No historical backfill is provided.
- No heatmap or liquidation price clusters are claimed.
- For production multi-instance deployments, replace SQLite with a managed database and use a single elected stream consumer or a durable message queue.
