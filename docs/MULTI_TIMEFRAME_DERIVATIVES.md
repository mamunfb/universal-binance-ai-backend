# Multi-Timeframe Derivatives Analysis

## API

```http
GET /api/v1/analysis/derivatives/multi-timeframe/BTCUSDT?periods=5m,15m,1h,4h,1d&limit=48
```

Each requested USD-M timeframe runs the existing Advanced Derivatives Analysis against locally stored open-interest, price, funding and liquidation observations. Allowed periods: 5m, 15m, 30m, 1h, 2h, 4h, 6h, 12h, 1d. Between 1 and 9 distinct periods can be selected. At least six locally stored OI records are required per period. No upstream exchange calls are performed by this endpoint.

## Agreement

The response reports independent sections, available/missing periods, OI rising/falling/flat lists and latest OI timestamps. It classifies `ALL_OI_RISING`, `ALL_OI_FALLING`, `ALL_OI_FLAT`, or `MIXED_OI_DIRECTIONS` only when all requested periods have completed analysis and all their latest OI timestamps are identical. Otherwise it reports `INCOMPLETE_COVERAGE`, `UNALIGNED_END_TIMESTAMPS`, `SINGLE_TIMEFRAME_ONLY`, or `UNAVAILABLE`.

Because OI periods are sampled independently, exact timestamp equality across 5m, 1h, and 1d is not guaranteed. This intentionally conservative check may withhold agreement even when markets appear directionally consistent. Price/OI timestamp alignment and completeness are not proven by matching end timestamps.

Each successful per-period analysis writes an idempotent signal snapshot to the configured SQLite store. Results are descriptive research evidence, not trade instructions, forecasts, or confidence probabilities.

## MCP

`analyze_multi_timeframe_derivatives`
