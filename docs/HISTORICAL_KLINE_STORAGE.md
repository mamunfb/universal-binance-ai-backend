# Historical Kline Storage

## Scope

The private backend can collect a bounded batch of Binance Spot, USDⓈ-M Futures, or COIN-M Futures candles and persist them in a local SQLite database. The store is idempotent by market, symbol, interval, and candle open time. Re-collecting an overlapping range updates the existing candle instead of creating duplicates.

This is a local historical OHLCV cache, not an exchange archive. It does not run a background backfill, infer missing candles, or guarantee continuous coverage. The API currently collects the latest exchange window returned by the provider (maximum 1,000 Spot candles or 1,500 Futures candles per request).

## Configuration

Optional environment variable:

```env
HISTORICAL_KLINE_DATABASE_PATH=data/historical_klines.sqlite3
```

The database directory is created when the service starts. Back up this SQLite file if its history is important. The service does not currently implement automatic retention or archival.

## Collect candles

```http
POST /api/v1/history/klines/{market}/{symbol}/collect?interval=1h&limit=500
```

Supported market values: `SPOT`, `USD_M`, `COIN_M`.

- Spot limit: 1–1,000.
- Futures limit: 1–1,500.
- Supported intervals follow the Binance kline interval set exposed by the API.
- Collection uses public exchange market data; no Binance trading key is required.
- This POST only stores market data locally. It does not place or modify orders.

## Read stored candles

```http
GET /api/v1/history/klines/{market}/{symbol}?interval=1h&limit=1000
```

Optional filters: `start_time_ms`, `end_time_ms` (inclusive candle open-time bounds). Read limit: 1–5,000. Rows are returned oldest-to-newest.

The response includes source and collection time for each candle. `coverage.contiguous` is deliberately null: the store does not yet verify interval-by-interval gaps, so a returned range must not be assumed complete.

## Validation and limitations

- Rejects malformed rows, non-finite prices/volumes, invalid OHLC relationships, negative volumes, invalid timestamps, and duplicate open times within one collection batch.
- Uses SQLite primary-key upserts to make overlapping collection idempotent.
- This first iteration does not persist funding rates or open-interest history, run scheduled collection, or perform backtests.
- No profitability, forecast, or trading recommendation is produced.


## Historical coverage inspection

Inspect an explicit, UTC-aligned candle-open range before using stored candles in research or backtests:

```http
GET /api/v1/history/klines/{market}/{symbol}/coverage?interval=1h&start_time_ms=...&end_time_ms=...
```

Both range endpoints are inclusive candle **open times** and must align to the selected interval. Fixed intervals use UTC epoch boundaries; weekly candles use Monday 00:00 UTC; monthly candles use the first day of each month at 00:00 UTC. The engine checks every expected candle open against the local store and groups consecutive missing candles into gap ranges.

Response status:
- `COMPLETE`: every expected open time in the requested range exists locally.
- `INCOMPLETE`: some, but not all, expected candles exist.
- `NO_STORED_DATA`: no expected candles exist in the requested range.

The response includes expected/stored/missing counts, coverage ratio, gap start/end open times, and any stored timestamps that do not fit the expected interval grid. Requests are capped at 100,000 expected candles to bound work. This is a local database completeness check, not proof that the exchange history itself is complete or that every stored candle is final/authentic. Backtests should reject or explicitly account for any range whose coverage status is not `COMPLETE`.


## Scheduled historical collector

The optional background collector can poll an explicit allow-list of market/symbol/interval series and persist new candles into the same idempotent SQLite store. It is disabled by default.

Configuration:

```env
HISTORICAL_KLINE_DATABASE_PATH=data/historical_klines.sqlite3
HISTORICAL_COLLECTOR_ENABLED=true
HISTORICAL_COLLECTOR_JOBS=[{"market":"SPOT","symbol":"BTCUSDT","interval":"1m"},{"market":"USD_M","symbol":"BTCUSDT","interval":"5m"},{"market":"COIN_M","symbol":"BTCUSD_PERP","interval":"1h"}]
HISTORICAL_COLLECTOR_POLL_SECONDS=30
HISTORICAL_COLLECTOR_INITIAL_LIMIT=500
```

The example jobs are illustrative only; confirm that each symbol is currently listed and tradable on the selected Binance market before enabling it. The job list is limited to 100 explicit series. Poll interval must be 10–3,600 seconds; initial limit must be 1–1,500 (Spot requests are capped at 1,000).

On first run for a series, the collector stores the latest configured initial window. On later runs it requests from the newest locally stored candle open time (inclusive), intentionally overlapping the latest candle so an exchange candle that was still forming can be updated. If the process was offline long enough to miss more than one REST response page, subsequent cycles continue from the latest stored timestamp until caught up. Repeated overlapping requests are safe because storage is keyed by market, symbol, interval, and candle open time.

Status endpoint:

```http
GET /api/v1/history/collector/status
```

The endpoint reports enabled/running state, configured jobs, cycle counts, last success, and per-job results. Failed jobs are recorded without stopping the other configured jobs.

Operational constraints:
- Enable only on an always-on process with persistent disk. Scale-to-zero services cannot provide continuous collection.
- Run one collector process per SQLite database. Multiple replicas can race and duplicate upstream requests.
- The collector is sequential, not a high-throughput bulk downloader. Keep the configured job list small and respect Binance request limits.
- The initial window is not a full historical backfill. Older history must be loaded separately and checked with the coverage endpoint.
- Collection is best-effort. Verify gaps with Historical Coverage Engine; do not assume every expected candle arrived.
- The latest candle may be incomplete while its interval is open. The collector deliberately refreshes it; downstream backtests should exclude candles that were not closed at the evaluation timestamp.
- This collector stores candles only. Funding-rate and open-interest history collectors are separate future work.
