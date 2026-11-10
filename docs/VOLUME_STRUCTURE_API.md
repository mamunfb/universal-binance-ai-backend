# Volume and Market Structure API

## Endpoint

`GET /api/v1/analysis/spot/volume-structure/{symbol}`

Example:
`/api/v1/analysis/spot/volume-structure/BTCUSDT?interval=1h&limit=300`

Parameters:
- `interval`: 15m, 1h, 4h, 1d
- `limit`: 20–1000 candles
- `anchor_index`: candle index from which anchored VWAP begins (0 is oldest returned candle)
- `profile_bins`: 5–200 fixed price bins
- `value_area_pct`: 0.50–0.95, default 0.70
- `pivot_left`, `pivot_right`: confirmed pivot window

## VWAP

VWAP uses each candle's typical price `(high + low + close) / 3` weighted by candle volume. The API calls this anchored VWAP because it begins at the selected candle index. It is not automatically a market-session VWAP; a proper session VWAP requires an explicit session boundary and timezone.

## Volume profile

The initial profile allocates each candle's full volume to the bin containing its typical price. It calculates:
- POC: bin with the largest allocated volume
- VAH / VAL: upper/lower edge of a contiguous value area grown from POC until the target volume share is met
- Per-bin volume and volume share

This is an OHLCV approximation, not trade-level volume-at-price or bid/ask delta. It cannot reveal precise intrabar volume distribution.

## Market structure

Confirmed symmetric local pivots are used as swing highs/lows. A candle close above an unbroken confirmed swing high is labeled bullish BOS if the current state is bullish/unconfirmed, otherwise bullish CHoCH. A close below an unbroken confirmed swing low is labeled bearish BOS if the current state is bearish/unconfirmed, otherwise bearish CHoCH.

Wick-through-and-close-back events are returned as liquidity sweep candidates. These labels are rule-based approximations; market-structure terminology varies among analysts and does not prove institutional activity.

## Limitations

- Binance Spot OHLCV only in this first implementation.
- No order-book heatmap, true trade-level volume profile, footprint, or bid/ask delta.
- No prediction, entry recommendation, or guarantee of support/resistance.
