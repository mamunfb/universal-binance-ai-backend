# Multi-Timeframe and BTC Market Context

## Multi-timeframe endpoint

`GET /api/v1/analysis/spot/multi-timeframe/{symbol}`

Fetches 250 Spot candles for each of 15m, 1h, 4h, and 1d and calculates the configured indicators per timeframe. A failed interval is reported separately and makes the overall status INCOMPLETE.

The trend labels are rule-based descriptions using close relative to EMA20 and EMA20 relative to EMA50. They are not validated forecasts.

## BTC market condition endpoint

`GET /api/v1/analysis/market/btc-condition`

Combines BTCUSDT and ETHUSDT multi-timeframe structures with their 24-hour Spot ticker change and quote volume. The regime label uses BTC 1d and 4h structure:
- BULLISH_TREND_CONTEXT
- BEARISH_TREND_CONTEXT
- MIXED_OR_TRANSITIONAL
- UNKNOWN

This is not a full global crypto market regime model. BTC dominance, total market capitalization, stablecoin flows, macro events, and cross-exchange breadth are not included.

## Liquidation data scope

This release does not claim to provide a complete liquidation history or liquidation heatmap. Binance force-order liquidation events are delivered through a market-data WebSocket stream; a reliable implementation requires a continuously running stream consumer, reconnect handling, event-time storage, and explicit retention policy. That is a separate streaming component and is not represented by the REST snapshots in this release.
