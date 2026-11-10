# Price Levels API

## Endpoint

`GET /api/v1/analysis/spot/price-levels/{symbol}`

Parameters:
- `interval`: 15m, 1h, 4h, or 1d (default 1h)
- `limit`: 20–1000 candles (default 300)
- `pivot_left`, `pivot_right`: confirmed local pivot window (default 3)
- `tolerance_pct`: price clustering tolerance (default 0.003 = 0.3%)

## Support and resistance

The service finds confirmed local highs/lows using a symmetric left/right pivot window, then groups nearby prices within the configured percentage tolerance. It reports the mean price and touch count for each cluster. Levels are sorted nearest-first above/below the latest close. They are historical reference zones, not guaranteed barriers.

A pivot is not confirmed until the configured number of candles to its right have closed. The newest right-window candles are therefore excluded from confirmed pivots.

## Fibonacci

The service selects the latest confirmed pivot and pairs it with the latest preceding opposite pivot. It reports retracement ratios 0, 0.236, 0.382, 0.5, 0.618, 0.786, 1 and extension ratios 1.272, 1.618, 2.0. Different swing-selection rules can produce different levels; the output is not a forecast.

## Limitations

- Spot candles only in this initial API.
- No order-book liquidity zones, volume profile, or market-structure break confirmation yet.
- A cluster touch count is not proof of institutional support/resistance.
- The calculations do not include fees, slippage, or trade execution.
