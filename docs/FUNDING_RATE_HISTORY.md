# Historical Funding Rate Storage

## Scope

The backend can manually collect and locally store Binance USDⓈ-M funding-rate events. Events are keyed by market, symbol, and funding timestamp. Repeated overlapping collection is idempotent and updates an existing event at the same timestamp.

This first version supports USD-M only. COIN-M funding history is not enabled here. Collection uses public market data; no Binance trading key is required. The feature is research-only and does not place or modify orders.

## Configuration

```env
FUNDING_RATE_DATABASE_PATH=data/funding_rates.sqlite3
```

The SQLite database directory is created automatically.

## Collect funding events

```http
POST /api/v1/history/funding-rates/USD_M/{symbol}/collect?start_time_ms=...&end_time_ms=...&limit=1000
```

- `start_time_ms` and `end_time_ms` are optional inclusive millisecond timestamps.
- Limit is 1–1,000 events per request.
- If no time bounds are supplied, Binance returns its latest available events up to the requested limit.
- Empty upstream responses return `NO_NEW_DATA`; no rows are written.

The API currently performs one bounded request per call. It does not yet run an automatic funding collector or paginate an arbitrarily long date range.

## Read stored events

```http
GET /api/v1/history/funding-rates/USD_M/{symbol}?start_time_ms=...&end_time_ms=...&limit=1000
```

The read limit is 1–5,000 events. Returned events are ordered oldest-to-newest and include funding timestamp, funding rate, optional mark price, original source, and collection timestamp.

The response reports observed time deltas between adjacent stored events. It deliberately does not classify these as missing events: funding intervals can differ by contract and can change over time, so a universal fixed interval would create false gap alerts. `expected_schedule_verified` therefore remains false.

## Data validation and limitations

- Rejects malformed rows, invalid/negative timestamps, non-finite rates, non-finite mark prices, and non-positive mark prices.
- Duplicate timestamps within one provider response are rejected.
- SQLite upsert key: `(market, symbol, funding_time_ms)`.
- No automatic schedule inference, gap-completeness guarantee, full historical backfill, or background collector is included in this iteration.
- Historical API results represent locally stored data only. Verify source, time range, and collection completeness before research or backtesting.
