# Multi-Timeframe Order Flow Intelligence

## Endpoint

`GET /api/v1/analysis/order-flow/multi-timeframe/{market}/{symbol}`

Default request:

```text
GET /api/v1/analysis/order-flow/multi-timeframe/USD_M/BTCUSDT?periods=5m,15m,1h,4h,1d&bin_size_bps=5&value_area_pct=70
```

Supported rolling windows: `5m`, `15m`, `30m`, `1h`, `2h`, `4h`, `6h`, `12h`, and `1d`. Select 1–9 unique periods. The same as-of timestamp is used for all windows.

## Returned comparison

Each timeframe reports:

- Window start/end and observed first/last trade timestamps.
- Number of locally stored trades and whether the window has enough data.
- Net CVD quantity and notional proxy.
- Aggressive buy/sell quantity imbalance.
- Price/CVD divergence candidate.
- POC and Value Area boundaries when data is available.

The top-level `cvd_agreement` describes whether the signs of net CVD match across requested windows. Missing data yields `INSUFFICIENT_TIMEFRAME_DATA`. Agreement is not a vote or a forecast: rolling windows overlap and are not independent confirmations.

The MCP tool is `analyze_multi_timeframe_order_flow`.

## Data source and coverage

The endpoint reads only locally persisted aggregate trades. It queries at most 50,000 rows over the longest requested period. The optional aggregate-trade collector must be enabled and configured for the same market and symbol. Collection is disabled by default and no historical backfill is performed. A timeframe may be marked `COMPLETED` while still having incomplete exchange coverage; inspect observed timestamps and `collector_coverage.limit_reached`.

## Limitations

- CVD is reset independently at each rolling window's start.
- POC, VAH and VAL are dependent on the configured bucket width and observed notional proxy.
- Overlapping windows are statistically dependent; apparent agreement does not provide independent confirmation.
- Aggregate trade records do not identify individual traders, institutional participants, order intent, or hidden liquidity.
- COIN-M notional remains a raw price-times-contract-quantity proxy; contract face value is not applied.
- The output is descriptive research, not a validated trading strategy, probability, forecast, or financial advice.
