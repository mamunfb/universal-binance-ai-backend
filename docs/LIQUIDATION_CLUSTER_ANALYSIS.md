# Liquidation Cluster Analysis

## Endpoint

`GET /api/v1/analysis/futures/liquidation-clusters/{symbol}?limit=5000&bucket_bps=25`

Optional `start_time_ms`, `end_time_ms`, and `min_events` constrain the analysis.

## Method

Observed USD-M force-order snapshots are grouped into logarithmic price buckets. The bucket width is configurable in basis points. Each cluster reports observed event count, approximate notional, BUY/SELL side breakdown, time bounds and share of clustered notional.

Force-order SELL is shown as a long-position liquidation-side candidate; BUY is shown as a short-position liquidation-side candidate. These are candidate labels based on the forced order side, not independently verified position attribution.

## Coverage and limitations

- Uses only locally stored liquidation events; it does not collect data.
- The upstream force-order stream is a partial snapshot feed. It must not be treated as a complete liquidation tape.
- The collector is opt-in and disabled by default.
- History starts only after the collector is enabled and running.
- Approximate notional uses stored cumulative filled quantity multiplied by average fill price.
- If the query reaches its event limit, `coverage.truncated_at_limit` is true.
- Clusters describe observed events and do not predict future liquidation levels or price direction.
