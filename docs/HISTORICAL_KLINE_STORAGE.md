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
