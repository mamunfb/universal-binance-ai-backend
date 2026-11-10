# Market Structure + Order Flow Confluence

## Endpoint

`GET /api/v1/analysis/market-structure-confluence/{market}/{symbol}`

Parameters:
- `interval`: local candle interval, default `1h`.
- `limit`: 40–1000 candles, default 300.
- `periods`: 1–9 unique order-flow windows, default `15m,1h,4h,1d`.
- `bin_size_bps`: volume-profile bucket width, default 5.
- `value_area_pct`: volume-profile value area target, default 70.

Example:

```bash
curl -H "Authorization: Bearer $PERSONAL_API_KEY" \
  "https://YOUR_PRIVATE_API_HOST/api/v1/analysis/market-structure-confluence/USD_M/BTCUSDT?interval=1h&limit=300&periods=15m,1h,4h,1d"
```

## Inputs combined

- Market structure: OHLC-derived swing structure and latest BOS/CHoCH close-through candidate.
- Market regime: fixed volatility/path-efficiency heuristic and recent price-path direction.
- Order flow: one-hour locally captured aggregate-trade CVD.
- Multi-timeframe order flow: CVD sign and volume profile context for the requested rolling windows.
- Liquidity sweep: latest OHLC wick/reclaim candidate, with locally captured trade and sampled order-book context.

## Output interpretation

The response reports:
- `bias`: BULLISH, BEARISH, MIXED, or UNKNOWN.
- `alignment`: whether available directional source classifications agree or conflict.
- Counts of bullish, bearish, directional and available source classifications.
- Each source's status, direction and compact evidence detail, including structure swing levels/BOS-CHoCH, regime metrics, CVD divergence, POC/VAH/VAL, per-timeframe flow coverage, and the latest sweep's aggressor-flow/order-book/derivatives context when available.
- Local data coverage and query caps.

A missing or neutral source contributes no vote; it is not counted as evidence for the opposite direction. A source that reports a descriptive status but no directional label can still appear as available without affecting the directional count. Counts are not weighted confidence, calibrated probability, or statistical independence.

## Important limitations

- All inputs are derived from local stored data. Collector downtime, disabled collectors, gaps and query caps can reduce coverage; no backfill is performed by this endpoint.
- Multi-timeframe windows overlap and are not independent confirmations.
- OHLC structure, market regime and sweep classifications are fixed heuristics, not validated predictors.
- Aggregate-trade CVD does not identify trader identity or intent.
- The engine does not infer institutional activity, resting stop orders, spoofing, or liquidation intent.
- No trade probability, entry, stop, target, leverage or investment recommendation is generated.

## MCP

Read-only MCP tool: `analyze_market_structure_confluence`. It calls the REST endpoint; it does not duplicate the analysis engine or execute trades.
