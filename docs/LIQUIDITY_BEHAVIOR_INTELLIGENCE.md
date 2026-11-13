# Liquidity Behavior & Aggregate Trade Flow Intelligence

## What it adds

This feature pairs the locally sampled order book with Binance aggregate trade streams to calculate:

- Aggressive buyer/seller notional proxies from the aggregate trade `m` flag.
- Net taker-flow imbalance for the interval between the latest two stored depth samples.
- Changes in visible bid/ask depth between those snapshots.
- Large price-level quantity reductions with little matched aggressive trade flow, labelled as liquidity-withdrawal candidates.
- High aggressive trade flow with limited midpoint movement and retained opposite-side displayed depth, labelled as absorption candidates.

It is intentionally a candidate-analysis layer, not a manipulation detector or a validated execution signal.

## Enable the collectors

Both order-book and aggregate-trade collection should be enabled for the same market/symbol. The aggregate-trade collector is disabled by default.

```dotenv
ORDER_BOOK_COLLECTOR_ENABLED=true
ORDER_BOOK_COLLECTOR_JOBS=[{"market":"USD_M","symbol":"BTCUSDT"}]

AGGREGATE_TRADE_COLLECTOR_ENABLED=true
AGG_TRADE_COLLECTOR_JOBS=[{"market":"USD_M","symbol":"BTCUSDT"}]
# Optional SQLite fallback path; DATABASE_URL selects PostgreSQL/Neon when configured.
AGGREGATE_TRADE_DATABASE_PATH=data/aggregate_trades.sqlite3
```

When DATABASE_URL is configured, both collectors use PostgreSQL/Neon; otherwise they use their configured SQLite fallback paths. SQLite requires persistent disk. Run one collector-owning application process for each configured market/symbol job set to avoid duplicate WebSocket subscriptions and duplicate samples, including when PostgreSQL is shared. The process must remain alive. The trade collector stores public aggregate trades only from enablement onward; it does not backfill.

## APIs

- `GET /api/v1/history/aggregate-trades/status`
- `GET /api/v1/history/aggregate-trades/{market}/{symbol}?limit=1000`
- `GET /api/v1/analysis/liquidity-behavior/{market}/{symbol}`

Analysis parameters:
- `min_removed_notional` (default 10000)
- `min_aggressive_notional` (default 10000)
- `max_absorption_move_bps` (default 2)
- `trade_price_band_bps` (default 2)

The analysis endpoint compares the latest two stored order-book samples and aggregate trades whose trade timestamps fall between those samples. It returns insufficient data if fewer than two depth samples exist.

## MCP tools

- `get_aggregate_trade_collector_status`
- `get_stored_aggregate_trades`
- `analyze_liquidity_behavior`

## Interpretation details

Binance aggregate trade messages include `m` ("is the buyer the market maker"). When true, the buyer was maker and the aggressor/taker side is inferred as SELL; when false, the taker side is inferred as BUY. This is a public trade-side inference, not participant identity.

A visible level reduction is matched to opposite-side aggressive trades within a configurable price band. If matched trade value is below 25% of the removed price-times-quantity value, it is labelled `PULLING_CANDIDATE_LOW_MATCHED_TRADE_FLOW`; otherwise it is `TRADE_CONSUMPTION_OR_MIXED`. This heuristic can miss trades between samples and cannot establish intent.

Absorption candidates require the configured aggressive trade value, midpoint movement no greater than the configured basis-point threshold, and at least 80% of the prior visible notional remaining on the resting side. This can also be caused by replenishment, new orders, sampling timing, or other market activity.

## Limitations

- Depth sampling is periodic; transient additions/removals between samples may be missed.
- The analysis uses only the latest pair of sampled depth snapshots and does not reconstruct every event.
- AggTrade aggregates fills and does not expose account identity, hidden orders, or all market events.
- Price-band trade matching is approximate, not order-level attribution.
- The default thresholds are operator-configurable heuristics, not empirically calibrated.
- For COIN-M, price × contract quantity is a raw proxy; contract face value/multiplier is not applied.
- Spot and Futures markets are analyzed independently; no cross-exchange or cross-market consolidated tape is built.
- No trade execution, order placement, or financial recommendation is performed.

## Official Binance protocol references

- [Spot Aggregate Trade Stream](https://developers.binance.info/en/docs/catalog/core-trading-spot-trading/api/ws-streams/~)
- [USD-M Futures Aggregate Trade Stream](https://developers.binance.info/docs/derivatives/usds-margined-futures/websocket-market-streams/All-Market-Mini-Tickers-Stream)
- [COIN-M Futures Aggregate Trade Stream](https://developers.binance.info/en/docs/catalog/core-trading-derivatives-trading-coin-m-futures/api/ws-streams)
