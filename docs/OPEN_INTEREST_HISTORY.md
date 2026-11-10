# Historical Open Interest Storage

## Scope

The backend supports manual collection and local storage of Binance USDⓈ-M historical open-interest statistics. The stored series is separated by market, symbol, and period, with timestamp as the event key. Repeated collection of the same timestamp is idempotent and updates that record.

The Binance endpoint is `GET /futures/data/openInterestHist`. Supported periods are `5m`, `15m`, `30m`, `1h`, `2h`, `4h`, `6h`, `12h`, and `1d`. Binance documents a maximum request limit of 500 and availability of only the latest month of data. It also notes that periods with no trades may be omitted; such absences are expected and are not backfilled. See the [official USD-M Futures API documentation](https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Open-Interest-Statistics).

This implementation supports USD-M only. It does not currently provide a background Open Interest collector or full historical backfill.

## Configuration

```env
OPEN_INTEREST_DATABASE_PATH=data/open_interest.sqlite3
```

## Collect

```http
POST /api/v1/history/open-interest/USD_M/{symbol}/collect?period=1h&limit=500
```

Optional inclusive millisecond bounds: `start_time_ms` and `end_time_ms`. The API makes one bounded upstream request per call. Maximum limit is 500. An empty upstream response returns `NO_NEW_DATA` and stores nothing.

## Read

```http
GET /api/v1/history/open-interest/USD_M/{symbol}?period=1h&limit=500
```

Read limit is 1–5,000. Records are returned oldest-to-newest with timestamp, total open interest (`sumOpenInterest`), open-interest value (`sumOpenInterestValue`), optional CMC circulating supply, source, and collection timestamp.

## Coverage and integrity

Observed timestamp deltas are included for inspection, but are not classified as missing records. Binance explicitly says periods with no trades may be omitted, so a strict continuous-time gap detector would report false positives. The response sets `expected_schedule_verified=false`.

The store validates finite, non-negative metrics, timestamps, symbol consistency, supported periods, and duplicate timestamps within a provider batch. SQLite upsert key: `(market, symbol, period, timestamp_ms)`.

Open interest is a market-wide aggregate statistic for the selected contract and period; it is not a count of traders or a directional Buy/Sell signal. Stored history is only as complete as the data retrieved and successfully saved during Binance's documented availability window.
