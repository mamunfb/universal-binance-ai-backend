# Smart Money Market Structure (OHLC heuristics)

## Endpoint

`GET /api/v1/analysis/smart-money-structure/{market}/{symbol}?interval=1h&limit=300&swing_left=3&swing_right=3`

MCP tool: `analyze_smart_money_market_structure`.

## Calculated candidates

- **Swing highs/lows:** strict local extrema with configurable left/right candle confirmation. A pivot is only known after the right-side candles close.
- **BOS / CHoCH:** a close-through of the latest confirmed opposing swing. The BOS/CHoCH label uses the recent higher-high/higher-low or lower-high/lower-low heuristic.
- **Liquidity sweep candidates:** a wick beyond a recent confirmed swing followed by a close back across the level.
- **Fair Value Gap candidates:** three-candle non-overlap gaps; later OHLC candles classify each as unmitigated, partially mitigated or fully filled.
- **Order block candidate:** the last opposite-colour candle in a 20-candle lookback when the latest candle confirms a close-through.
- **Premium / discount:** current close relative to the midpoint of the full requested sample high-low range.

## Interpretation and limits

These are reproducible OHLC-based heuristics, not proof of Smart Money, institutional activity, resting liquidity, or actual order blocks. The calculation has no order book, tick-level trades, participant identity or exchange intent. Different charting conventions may define pivots, BOS, CHoCH, FVG and order blocks differently.

The premium/discount calculation uses the requested sample's high/low, not a validated dealing range. Missing or non-contiguous candles can distort all structure calculations. The engine produces no forecast, probability, entry, stop, target or trading recommendation.

Use locally collected candles. The endpoint does not fetch or collect market data.
