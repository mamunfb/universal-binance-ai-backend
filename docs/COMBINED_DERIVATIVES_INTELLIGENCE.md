# Combined Derivatives Intelligence

## Endpoint

```http
GET /api/v1/analysis/derivatives/combined/BTCUSDT?period=1h&limit=100
```

## Inputs and alignment

The analysis reads local SQLite histories for USD-M open interest, global long/short account ratio and taker buy/sell ratio. It joins these series on exact timestamp equality. At least two exact timestamp intersections are required for a completed report. No forward filling, interpolation or nearest-neighbour matching is used. Consequently, an incomplete report is expected when the three collectors have not captured the same periods.

The report includes percentage change over the common aligned window, latest account-ratio comparison, latest taker-volume comparison and OI values. It does not imply that account counts equal position size or that taker flow predicts future price direction.

## Funding context

Funding events have a different sampling schedule from ratio observations. The latest locally stored funding event inside the OI history window is displayed separately. It is not joined to every ratio timestamp and is not treated as a per-candle measurement.

## MCP

`analyze_combined_derivatives_intelligence` reads the API. It does not trigger collection.

## Data requirements and limits

- Manually collect and store OI, global account ratio and taker ratio for the same symbol and period.
- Funding history is optional for the core aligned comparison; it is shown when present.
- The local database begins accumulating data only after collection is performed.
- Results are descriptive research evidence, not trade instructions, price forecasts or calibrated probabilities.
