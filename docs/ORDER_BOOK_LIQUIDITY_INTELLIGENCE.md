# Order Book & Liquidity Intelligence

## Endpoint

`GET /api/v1/analysis/order-book/{market}/{symbol}?limit=100&wall_multiplier=3`

Supported markets: `SPOT`, `USD_M`, `COIN_M`. The MCP equivalent is `analyze_order_book_liquidity`.

## Metrics

- Best bid, best ask, mid-price, absolute spread and spread in basis points.
- Bid/ask notional and quantity across the returned visible levels.
- Depth imbalance: (bid notional - ask notional) / (bid notional + ask notional).
- Top-of-book microprice and deviation from midpoint.
- Near-mid visible depth bands at 5, 10, 25, 50 and 100 basis points.
- Cumulative visible notional by price level.
- Large visible order candidates, using a configurable multiple of the median level notional on that side.

## Large-order heuristic

A level is flagged when its price-times-quantity notional is at least `wall_multiplier` times the median notional among valid returned levels on the same side. This relative threshold is transparent but not statistically calibrated. It does not prove spoofing, institutional activity, support/resistance or intent.

## Data limitations

- The endpoint fetches a single public REST snapshot per request; it is not a synchronized WebSocket depth stream.
- Visible orders can be changed or cancelled and do not guarantee executable liquidity.
- Hidden liquidity, participant identity and order intent are not available.
- Imbalance and microprice are descriptive pressure proxies, not price predictions.
- Historical liquidity change tracking is not included. A future stream collector would need sequence-aware snapshot/delta synchronization and persistent storage.
- The endpoint does not submit, modify or cancel orders.
