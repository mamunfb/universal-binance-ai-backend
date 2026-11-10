# Liquidity Sweep Confirmation Engine

## Endpoint

`GET /api/v1/analysis/liquidity-sweep-confirmation/{market}/{symbol}`

Query parameters:
- `interval`: locally stored candle interval; default `5m`.
- `limit`: candle sample size, 30–1000; default 300.
- `equal_level_tolerance_bps`: swing clustering tolerance in basis points; default 8.

Example:

```bash
curl -H "Authorization: Bearer $PERSONAL_API_KEY" \
  "https://YOUR_PRIVATE_API_HOST/api/v1/analysis/liquidity-sweep-confirmation/USD_M/BTCUSDT?interval=5m&limit=300"
```

## Evidence model

1. **OHLC sweep candidate:** a candle wick crosses a previously confirmed local swing high/low and its close returns inside the level.
2. **Equal-high/equal-low zones:** swing pivots clustered within the configured basis-point tolerance. These are price-level candidates, not observed stop orders.
3. **Aggressor-flow context:** locally stored aggregate trades during the five minutes after the sweep candle opens; buy/sell quantity and net CVD are reported.
4. **Volume profile:** post-sweep aggregate trades are used to calculate a local notional-proxy POC and value area (VAH/VAL), when enough valid trades exist. This profile is scoped to the confirmation window, not the whole candle sample.\n5. **Order-book context:** visible bid/ask notional is compared only when two stored samples are within the explicit timestamp tolerance. The samples are local snapshots, not a full historical depth reconstruction.
6. **Derivatives context:** nearest stored OI and funding observation within 60 minutes of the sweep timestamp. No forward-fill or interpolation is used. These are context fields, not directional confirmation.

The output labels a candidate `MULTI_SOURCE_CANDIDATE` only when both aligned aggressor flow and paired sampled-depth evidence exist; otherwise it reports `SINGLE_SOURCE_CANDIDATE` or `OHLC_ONLY_CANDIDATE`. This is an evidence-count label, not a probability or validated signal score.

## Data sources and limitations

- Candles come from the local historical kline store. The collector is optional; returned candles can contain gaps.
- Aggregate trades and order-book samples are locally captured only. Collectors are opt-in, have no historical backfill, and may have downtime or query caps.
- OI and funding context is loaded only for `USD_M`; absence of an aligned record is returned as null.
- A wick beyond a swing and a close back inside does not prove that stop orders were triggered.
- Equal highs/lows do not reveal resting stop orders.
- Aggressor flow does not reveal participant identity or intent.
- Sampled order-book changes do not prove spoofing, manipulation, absorption, or institutional activity.
- OI is aggregate and does not identify which side initiated positions. Funding is sparse and may not align with a sweep timestamp.
- The engine does not calculate probability, entries, stops, targets, or trade recommendations.

## MCP

The read-only MCP tool is `analyze_liquidity_sweep_confirmation`. It calls the canonical REST endpoint and does not duplicate the analysis engine.
