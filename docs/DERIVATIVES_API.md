# Futures Derivatives Intelligence

## USD-M Futures endpoint

`GET /api/v1/analysis/futures/usdm/derivatives/{symbol}`

Query parameters:
- `period`: `5m`, `15m`, `30m`, `1h`, `2h`, `4h`, `6h`, `8h`, `12h`, or `1d`
- `history_limit`: 1 to 100 records
- `order_book_limit`: 5, 10, 20, 50, 100, 500, or 1000

The response independently reports success/failure for:
- Funding rate history
- Current open interest
- Open interest history
- Global long/short account ratio
- Taker buy/sell volume ratio
- Order book snapshot and derived spread/depth summary

If one data source fails, other successful sections are still returned and the overall status is INCOMPLETE. This endpoint currently supports USDⓈ-M Futures only.

## Interpretation cautions
- Global long/short account ratio is account-count based, not a position-size ratio.
- Open interest alone does not identify whether new positions are long or short.
- Funding is not a standalone directional signal.
- Order book data is a snapshot; visible liquidity can change or be cancelled.
- Order book depth excludes Retail Price Improvement orders according to Binance documentation.
- No liquidation-feed or historical liquidation endpoint is included in this version.
