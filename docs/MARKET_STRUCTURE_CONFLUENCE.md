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


## Snapshot history and outcomes

- Save a selected analysis: `POST /api/v1/history/market-confluence/snapshots` with the complete analysis response.
- Read snapshots: `GET /api/v1/history/market-confluence/{market}/{symbol}?interval=1h&limit=100`.
- Evaluate forward outcomes: `GET /api/v1/analysis/market-confluence-performance/{market}/{symbol}?interval=1h&price_interval=1h&limit=200`.
- The analysis response includes `analyzed_at_ms` and a reference close only when the candle was fully closed at analysis time.
- Future evaluation uses candles with `open_time_ms > analyzed_at_ms`; absent future observations remain pending.
- MIXED/UNKNOWN snapshots are retained but excluded from directional aggregates. Directional-positive fraction is descriptive, not a validated strategy hit rate.
- No execution, fees, slippage, funding, leverage, stop or target simulation is included.

## Dashboard

The same-origin dashboard is served at `/dashboard`. Use HTTPS and a strong private API key. Do not put credentials in prompts or public client-side source.


### Forward comparison horizons

The performance endpoint now evaluates seven fixed horizons from each saved snapshot: 1 hour, 4 hours, 24 hours, 48 hours, 72 hours, 15 days (360 hours), and 30 days (720 hours). The 30-day horizon is a fixed 720-hour period, not a calendar month.

The default comparison candle is 1h, so the endpoint compares the market using hourly OHLC candles. Optional resolutions are 15m, 30m, 2h, 4h, 6h, 8h, 12h and 1d. 1m, 3m and 5m are intentionally excluded because a 30-day query would exceed the local 5,000-candle history query limit and could silently truncate the early part of the comparison window.

Each horizon reports sample count, pending observations, missing reference prices, directional-positive fraction, average directional return, favorable/adverse excursion, and candle continuity coverage. A horizon is not a completed observation until a local candle closes at or after its target time. Partial or gapped candle sequences are flagged and are not silently filled.


## Snapshot Price Path API

For one selected saved confluence snapshot, the dashboard can request a bounded local OHLC path:

`GET /api/v1/history/market-confluence/{market}/{symbol}/{snapshot_id}/price-path?price_interval=1h&hours=720`

The endpoint returns future candles, percentage change from the stored reference price, candle-continuity coverage, and a descriptive comparison between the saved BULLISH/BEARISH bias and the final observed market move. MIXED/UNKNOWN biases are not assigned a directional comparison. The dashboard defaults to 1-hour candles over up to 30 days; 15m, 30m, 2h and 4h are selectable. Only one selected snapshot is loaded at a time to bound response size. If the target horizon has not matured, the API reports a pending status rather than treating partial data as a completed outcome. Local candle gaps are reported and never interpolated. This is a descriptive historical visualization, not a strategy backtest or trading signal.


## Bias-specific historical accuracy

The forward performance endpoint reports a `bias_breakdown` for every horizon (1h, 4h, 24h, 48h, 72h, 15d and 30d). BULLISH and BEARISH snapshots have separate sample counts, directional-positive fraction, mean directional return and complete-candle-coverage count. MIXED and UNKNOWN snapshots remain visible in the sample breakdown but do not receive a directional accuracy percentage. These are descriptive historical outcomes for the locally stored snapshots and candles, not a validated prediction hit rate or strategy profitability estimate. Interpret the percentages together with sample size and coverage completeness.

## Regime-stratified historical outcomes

The forward-performance response now includes `regime_breakdown` for each horizon. It groups completed snapshot outcomes independently by the saved `market_regime`, `volatility_regime`, and `structure_regime` labels found in the `MARKET_REGIME` evidence item. A missing label is reported as `UNCLASSIFIED`; the evaluator does not infer a regime from price outcomes.

Each group reports total and directional sample sizes, positive and negative directional outcomes, directional-positive fraction, mean directional return, and complete candle-coverage count. MIXED and UNKNOWN biases remain in the total sample but are excluded from directional aggregates.

These are descriptive historical summaries, not calibrated probabilities, validated strategy hit rates, or evidence that a regime causes an outcome. Read sample sizes and candle-coverage counts alongside every fraction; small groups can be unstable. The dashboard currently displays the market-regime dimension, while the API also exposes volatility- and structure-regime breakdowns.

 
## Combined regime, bias and horizon analysis

Each forward horizon now also returns `regime_bias_breakdown`. For each of the three saved regime dimensions, outcomes are grouped by regime label and then by BULLISH, BEARISH, MIXED or UNKNOWN bias. Each cell includes sample size, directional sample size, positive and negative counts, positive fraction, mean directional return, and complete candle-coverage count. Empty combinations remain visible with zero samples and null directional metrics.

The dashboard displays the market-regime-by-bias table separately for every horizon. The API includes equivalent nested breakdowns for volatility and structure regimes. Cross-groups can be very small; compare counts and coverage before interpreting percentages. These are retrospective descriptive statistics, not predictive probabilities.
