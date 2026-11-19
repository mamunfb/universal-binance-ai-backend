# Order Book & Liquidity Intelligence

## Endpoint

`GET /api/v1/analysis/order-book/{market}/{symbol}?limit=100&wall_multiplier=3`

Supported markets: `SPOT`, `USD_M`, `COIN_M`. The MCP equivalent is `analyze_order_book_liquidity`.

## Metrics

- Best bid, best ask, mid-price, absolute spread and spread in basis points.
- Bid/ask notional and quantity across the returned visible levels.
- Depth imbalance: (bid notional - ask notional) / (bid notional + ask notional).
- Top-of-book microprice and deviation from midpoint.
- Near-mid visible depth bands at 5, 10, 25, 50 and 100 basis points.
- Cumulative visible notional by price level.
- Large visible order candidates, using a configurable multiple of the median level notional on that side.

## Large-order heuristic

A level is flagged when its price-times-quantity notional is at least `wall_multiplier` times the median notional among valid returned levels on the same side. This relative threshold is transparent but not statistically calibrated. It does not prove spoofing, institutional activity, support/resistance or intent.

## Data limitations

- The endpoint fetches a single public REST snapshot per request; it is not a synchronized WebSocket depth stream.
- Visible orders can be changed or cancelled and do not guarantee executable liquidity.
- Hidden liquidity, participant identity and order intent are not available.
- Imbalance and microprice are descriptive pressure proxies, not price predictions.
- Historical liquidity change tracking is provided only by the optional stream collector described below; the single-snapshot REST endpoint does not provide history.
- The endpoint does not submit, modify or cancel orders.


# Real-Time Order Book Stream & Historical Liquidity

## Scope

The optional collector maintains a local order book from Binance diff-depth WebSocket updates and a REST depth snapshot. It supports Spot, USD-M Futures and COIN-M Futures. Each configured market/symbol is a separate stream job.

## Enablement

The collector is disabled by default. Configure a persistent single-process deployment and set:

```dotenv
ORDER_BOOK_COLLECTOR_ENABLED=true
ORDER_BOOK_COLLECTOR_JOBS=[{"market":"USD_M","symbol":"BTCUSDT"},{"market":"SPOT","symbol":"BTCUSDT"}]
# Optional SQLite fallback path; DATABASE_URL selects PostgreSQL/Neon when configured.
ORDER_BOOK_DATABASE_PATH=data/order_book_history.sqlite3
ORDER_BOOK_SAMPLE_INTERVAL_SECONDS=1
ORDER_BOOK_SNAPSHOT_LIMIT=1000
ORDER_BOOK_STORED_LEVELS=20
```

Use only symbols valid for the selected market. When DATABASE_URL is set, samples are stored in the shared PostgreSQL/Neon database; otherwise the configured SQLite path is used and its directory must be writable and persistent. Run one collector-owning process per configured stream job set: multiple API replicas can duplicate WebSocket subscriptions and samples even when they share PostgreSQL. The collector must run on an always-on process; a scale-to-zero or short-lived host cannot provide continuous capture.

## Synchronization and recovery

- Open the market-specific diff-depth stream and buffer updates while fetching a REST depth snapshot.
- Discard buffered events already covered by snapshot `lastUpdateId`.
- Require the first applied update range to bridge `lastUpdateId + 1`.
- For Spot, reject a gap where the next event's `U` exceeds local update ID + 1.
- For USD-M and COIN-M, require each subsequent event's `pu` to equal the previous applied `u`.
- On disconnect, malformed sequence, or gap, discard the in-memory book and reconnect with a fresh snapshot.
- Zero quantity removes a price level; positive quantity replaces its absolute visible quantity.
- Keep at most the configured snapshot depth in memory and sample the top configured levels at the configured cadence.

The initial REST snapshot is limited to at most 1000 levels per side in this implementation. USD-M depth streams use Binance's current `/public/ws/` route. Binance documents that Retail Price Improvement (RPI) orders are not visible in the standard futures depth stream. Levels outside that initial snapshot are not known until subsequent stream updates report them. A local book is therefore a bounded visible-depth view, not a complete representation of every resting order.

## APIs

- `GET /api/v1/history/order-book/status` — collector status and sample count.
- `GET /api/v1/history/order-book/{market}/{symbol}?limit=100` — locally stored samples, newest first.
- Optional filters: `start_time_ms`, `end_time_ms`.

Each sample includes event/update identifiers, best bid/ask, midpoint, spread bps, bid/ask notional, imbalance and stored top levels. The history endpoint does not trigger collection or backfill.

## MCP tools

- `get_order_book_stream_status`
- `get_stored_order_book_history`

## Limitations

- Collection starts only after the feature is deployed and explicitly enabled; no earlier history is reconstructed.
- Sampling is periodic (default one second), not every depth event. Short-lived changes between samples may not appear in stored history.
- With SQLite fallback, persistent disk and one writer are required. With PostgreSQL/Neon, local disk persistence is not required for samples, but a single collector owner is still needed to avoid duplicate streams and samples across replicas.
- Stream availability, network gaps and exchange limits affect coverage. Status and timestamps must be checked before interpreting history.
- Order book levels do not identify participants, hidden liquidity, intent, or whether an order will remain available.
- Liquidity withdrawal is a change in displayed depth, not proof of spoofing or manipulation.
- This is market-data research only; no order placement or execution simulation is included.

## Official protocol references

- [Binance Spot WebSocket diff-depth stream and local-book synchronization](https://github.com/binance/binance-spot-api-docs/blob/master/web-socket-streams.md)
- [Binance USD-M Futures Public diff-depth stream](https://developers.binance.info/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/ws-streams/public)
- [Binance COIN-M Futures depth stream](https://developers.binance.info/en/docs/catalog/core-trading-derivatives-trading-coin-m-futures/api/ws-streams)
