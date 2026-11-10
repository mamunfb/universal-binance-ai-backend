# Historical Market Regime Heuristic

## Endpoint

`GET /api/v1/analysis/market-regime/{market}/{symbol}?interval=1h&limit=200`

The endpoint reads only locally stored historical OHLC candles. It does not fetch or collect data.

## Method

- True range is calculated from high, low and the previous close, then divided by the current close.
- The latest 20-candle mean true-range percentage is compared with the median of prior rolling 20-candle windows.
- HIGH_VOLATILITY means the latest value is greater than 1.5 times that median; LOW_VOLATILITY means it is less than 0.5 times the median.
- Otherwise, structure is classified using 20-candle path efficiency: absolute net close move divided by the sum of absolute close-to-close moves. A value of at least 0.60 is labelled TREND; lower values are RANGE.
- A high/low volatility label takes priority over the structure label.

At least 40 stored candles and five prior volatility windows are required. If data or baseline is insufficient, the response reports UNKNOWN rather than guessing.

## Limitations

This is a fixed descriptive heuristic, not an empirically calibrated or predictive model. Thresholds have not been optimized. It does not forecast price, estimate probabilities, or issue trading signals. Data gaps in local storage are not silently filled; callers should inspect historical coverage separately.
