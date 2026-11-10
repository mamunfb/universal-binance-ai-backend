# Historical Signal Performance Evaluation

## Endpoint

`GET /api/v1/analysis/derivatives/signal-performance/{symbol}?period=1h&price_interval=1h&limit=500&round_trip_cost_bps=0`

The MCP equivalent is `evaluate_historical_signal_performance`.

## What it measures

For each locally stored completed USD-M derivatives-analysis snapshot, the evaluator measures subsequent price outcomes over 1-hour, 4-hour and 24-hour horizons:

- Gross close-to-close return from the last candle fully closed at or before the snapshot timestamp.
- Hypothetical net return after subtracting the caller-supplied round-trip cost assumption in basis points.
- Maximum favorable and adverse price excursions, based on candle highs/lows through the selected outcome candle.
- Sample size, mean/median gross return, mean hypothetical net return and positive-return fraction.
- Actual elapsed time to the selected completed candle close.

The outcome candle is the first later candle whose close timestamp reaches the horizon boundary. The actual elapsed time is returned because candle intervals may not align exactly with a requested horizon.

## Important interpretation

This is a forward-outcome study of descriptive snapshots, **not a strategy backtest**. Existing classifications do not encode a validated entry direction, entry rule, exit rule, position sizing, leverage or stop. Therefore the engine deliberately does not calculate directional accuracy or claim a trading win rate. Positive-return fraction is not signal hit rate.

The cost assumption is a simple deduction from each gross return; it is not a measured fee or slippage estimate. Funding payments, market impact, liquidity, execution timing and liquidation are not simulated.

## Data and coverage

- Reads only local `derivatives_signal_snapshots` and `historical_klines` SQLite stores.
- Snapshots without a prior fully closed baseline candle are skipped.
- Horizons without a completed future candle remain pending and are not counted as losses.
- Missing or selectively collected candles and snapshots can bias the sample.
- Existing signal history starts when snapshot storage was introduced; this endpoint cannot reconstruct signals that were never stored.
- Results are descriptive historical observations and do not establish future performance or provide financial advice.
