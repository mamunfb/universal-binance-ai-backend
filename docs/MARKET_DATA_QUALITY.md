# Market Data Quality & Reliability

## Endpoint

`GET /api/v1/quality/market-data/{market}/{symbol}?interval=1h&lookback_hours=168`

Supported markets: `SPOT`, `USD_M`, `COIN_M`. The candle interval must be a fixed interval from `1m` through `1d`; `lookback_hours` is bounded from 1 to 2160.

The report reads local SQLite databases only. It does not call Binance or backfill missing data.

## What is measured

- **Historical klines:** record count, latest candle open/close timestamp, freshness against a two-candle operational threshold, and expected UTC candle-open coverage over the requested lookback ending at the latest stored candle. A currently forming candle is labeled `IN_PROGRESS`, not stale. SQLite's primary key prevents duplicate candle keys.
- **Funding rates:** stored event count and latest funding timestamp. A 24-hour freshness threshold is an operational warning only; funding events are not treated as a fixed continuous stream.
- **Open interest:** stored count and latest timestamp for the selected period. For candle intervals not supported by the OI history store (such as 1m or 3m), the report explicitly falls back to `1h` and returns `period: 1h`. Freshness threshold is three actual stored periods.
- **Derivatives ratios:** latest timestamp and count across locally stored USD-M ratio records. A three-hour freshness threshold is used; different ratio types are not assumed synchronized.
- **Aggregate trades and order-book samples:** local record count and latest event timestamp. Ten minutes is used as an operational freshness threshold.

## Status semantics

- Candle status may be `HEALTHY`, `DEGRADED`, `STALE`, `NO_DATA`, or `UNKNOWN`.
- For funding, OI, ratio, trade and order-book sources, `freshness` is reported separately from `status`. When rows exist their continuity status is `NOT_MEASURABLE` unless the stored schema supports a defensible completeness check.
- A database/schema read failure is `UNKNOWN`, not `NO_DATA`.
- Collector status is reported separately by the API from the in-process collector objects and environment settings.

## Important limitations

1. All results describe local persistence, not live exchange availability or authenticity.
2. Freshness thresholds are configurable in code and are not Binance service-level guarantees.
3. Aggregate-trade records do not retain a completeness heartbeat or verified sequence range. A recent last trade cannot prove that no trades were missed.
4. Order-book samples are persisted after sequence synchronization, but this endpoint does not reconstruct every stream disconnect or missed sampling interval. Recent samples do not prove gap-free history.
5. Funding and OI history is only as complete as prior manual or scheduled collection. No automatic backfill is performed by this endpoint.
6. The endpoint reports a selected symbol and market; it is not a global exchange health monitor.

## MCP

The read-only MCP tool is `inspect_market_data_quality(market, symbol, interval, lookback_hours)`.

This is a research and operational diagnostic, not a trading signal.
