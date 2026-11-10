# Spot/Futures Basis Intelligence

## Endpoint

`GET /api/v1/analysis/spot-futures/basis/{symbol}`

Compares the latest Binance Spot price ticker with the Binance USDⓈ-M Futures price ticker for the same symbol. It also requests the most recent available USDⓈ-M funding-rate record.

## Fields

- `price_comparison.spot_price`: latest Spot ticker price returned by Binance.
- `price_comparison.futures_price`: latest USDⓈ-M Futures ticker price returned by Binance.
- `price_comparison.basis`: Futures price minus Spot price.
- `price_comparison.basis_percent`: basis divided by Spot price, multiplied by 100.
- `price_comparison.relationship`: `FUTURES_PREMIUM`, `FUTURES_DISCOUNT`, or `AT_PARITY`.
- `funding`: latest funding rate and funding timestamp when available.

## Status and data quality

Price comparison and funding are independent sections. If either price snapshot is unavailable or invalid, the response is `INCOMPLETE` and no basis is calculated. If price comparison succeeds but funding is unavailable, the basis remains available and overall status is `INCOMPLETE`.

Both price endpoints return independent ticker snapshots. They are not guaranteed to be captured at precisely the same instant; the response explicitly warns that timing differences can affect measured basis. The endpoint does not claim an atomic exchange snapshot.

## Interpretation cautions

- A positive basis means the sampled Futures price is above the sampled Spot price; a negative basis means it is below.
- Basis and funding are separate measurements and should not be treated as interchangeable.
- Neither value is a standalone trading signal or guaranteed forecast.
- The endpoint is read-only. It does not place orders, sign transactions, or execute trades.
