# Order Flow Intelligence

## Endpoint

`GET /api/v1/analysis/order-flow/{market}/{symbol}`

Parameters:

- `lookback_minutes`: 1–1440, default 60
- `bin_size_bps`: 0.1–500, default 5
- `value_area_pct`: 50–99, default 70

Example:

```text
GET /api/v1/analysis/order-flow/USD_M/BTCUSDT?lookback_minutes=60&bin_size_bps=5&value_area_pct=70
```

## Calculations

- **Volume Profile:** aggregate trade notional proxy is grouped into price buckets. POC is the bucket with the greatest observed notional. Value Area expands from POC toward the larger adjacent bucket until the requested share of observed notional is included; VAL and VAH are the lower and upper bucket boundaries.
- **CVD:** aggressive buyer quantity minus aggressive seller quantity, reset at the requested window start. A parallel notional-proxy delta is also returned.
- **Divergence candidate:** compares first-to-last observed trade price change with net CVD quantity. Opposing signs are labelled as candidates, not predictive signals.
- **Coverage:** reports requested and observed timestamps, returned row count, and whether the local query cap was reached.

The MCP tool is `analyze_order_flow_intelligence`.

## Data prerequisites

The API reads only locally stored aggregate trades from the optional Binance aggregate-trade collector. Enable `AGGREGATE_TRADE_COLLECTOR_ENABLED=true` and configure `AGG_TRADE_COLLECTOR_JOBS` for the requested market and symbol. Collection is disabled by default. Historical data is not backfilled, so the observed window may be incomplete even when the API returns `COMPLETED`.

## Limitations

- This is an analysis of locally captured public aggregate trades, not a complete exchange-wide trade tape. Collector downtime and the query cap can omit trades.
- CVD is window-relative, depends on observed trades, and is not an independent buy/sell prediction.
- POC/VAH/VAL are calculated from the selected price bucket size and observed notional proxy; changing `bin_size_bps` can change the levels.
- COIN-M contract quantity is not converted using contract face value. Its price-times-quantity notional and CVD-notional fields are raw proxies.
- Aggregate trade data does not reveal trader identity, institutional status, order intent, hidden orders, or whether trades were initiated by a particular named participant.
- Divergence is a descriptive candidate only. It is not a validated strategy, probability, forecast, or financial recommendation.

No order placement, trading, signing, or withdrawal is performed.
