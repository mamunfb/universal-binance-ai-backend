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
