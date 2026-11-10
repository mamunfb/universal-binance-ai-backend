# Universal Binance AI Backend

A private, single-owner, research-only backend for collecting public cryptocurrency market data, computing transparent technical indicators, and exposing structured analysis to ChatGPT, Google Gemini, Manus, Claude, and Perplexity.

## Project goals
- Scan eligible Binance Spot, USDⓈ-M Futures, and COIN-M Futures markets where public endpoints support the requested data.
- Normalize market data and report coverage, timestamps, failures, and missing fields.
- Provide technical indicators and multi-timeframe market context.
- Add external news feeds only after source and license review; on-chain and tokenomics providers remain planned.
- Expose one canonical REST/OpenAPI API for the owner's private use; build thin ChatGPT, Gemini, Manus, Claude, and Perplexity adapters around the same intelligence engine.
- Keep this project research-only: no order placement, withdrawals, or trading execution.

## Safety and data integrity
- Use public market-data endpoints by default; public data does not require a Binance API secret.
- Never commit API keys, API secrets, passwords, tokens, or environment files.
- Never invent prices, news, timestamps, probabilities, or backtest results.
- Every analysis response must include source, timestamp, freshness, coverage, missing data, and status.
- If evidence is unavailable, return UNKNOWN, INCOMPLETE, or NO TRADE rather than guessing.
- A catalyst score is not a probability. Report probabilities only after a documented and validated methodology.

## Planned architecture
Binance public APIs -> provider adapters and normalization -> analysis services -> REST API -> AI clients and MCP adapter.

## Market coverage
- Binance Spot: market scanner, 24-hour ticker summary, klines, EMA/RSI/MACD/Bollinger indicators.
- Binance USDⓈ-M Futures: perpetual contract scanner and klines.
- Binance COIN-M Futures: perpetual contract scanner and klines.
- Binance USDⓈ-M derivatives: funding history, open interest, global long/short account ratio, taker buy/sell ratio, and order-book snapshot summary.
- Spot/USDⓈ-M Futures comparison: latest price basis (premium/discount) plus latest funding-rate context; see docs/SPOT_FUTURES_BASIS_API.md.
- Unified research-only Market Evidence Snapshot combining multi-timeframe trend, Spot/Futures basis, derivatives, approximate volume structure, and configured news catalyst triage; it explicitly emits no Buy/Sell signal or probability. See docs/MARKET_EVIDENCE_API.md.
- Multi-timeframe Spot analysis (15m/1h/4h/1d) and a limited BTC/ETH market context endpoint.
- Optional Binance USDⓈ-M force-order WebSocket snapshot collector with SQLite persistence; disabled by default and explicitly documented as incomplete snapshot coverage.
- Local, idempotent SQLite storage for validated Spot, USDⓈ-M, and COIN-M historical OHLCV candles; bounded manual collection and read-only retrieval endpoints. See docs/HISTORICAL_KLINE_STORAGE.md.
- Spot pivot-based support/resistance clusters and Fibonacci retracement/extension levels.
- Anchored VWAP, OHLCV-approximated Volume Profile (POC/VAH/VAL), and rule-based BOS/CHoCH/liquidity-sweep candidates.

Futures coverage is based on exchangeInfo symbols marked TRADING and the selected quote asset. Scanner responses include coverage counts and data failures. See docs/FUTURES_API.md, docs/DERIVATIVES_API.md, docs/SPOT_FUTURES_BASIS_API.md, docs/MARKET_EVIDENCE_API.md, docs/MULTI_TIMEFRAME_API.md, docs/LIQUIDATION_COLLECTOR.md, docs/PRICE_LEVELS_API.md, and docs/VOLUME_STRUCTURE_API.md.

## Repository layout
- backend/ — API and application services
- providers/ — exchange and external data-source adapters
- analysis/ — indicators, screening, validation, and risk calculations
- integrations/ — AI client adapters
- mcp-server/ — private read-only Model Context Protocol adapter
- docs/ — architecture, source inventory, and operating rules
- tests/ — automated tests

## Upstream source projects
Upstream projects will be evaluated and integrated individually. They will not be blindly copied into this repository. Each source must have its license, maintenance status, security posture, and relevance reviewed first. See docs/REPOSITORY_IMPORT_PLAN.md.

## Current status
The repository includes Spot and Futures scanners/klines, a validated local historical OHLCV store for manually collected and optionally scheduled/resumable Spot/USD-M/COIN-M candle collection, with UTC-aligned gap and coverage inspection, plus local USD-M historical funding-rate event and open-interest statistics storage/read APIs, with an optional scheduled/resumable derivatives collector, Spot technical indicators, USDⓈ-M derivatives snapshots, Spot/Futures basis and funding comparison, a unified research-only Market Evidence Snapshot, multi-timeframe Spot analysis, a limited BTC/ETH context endpoint, and an opt-in liquidation snapshot collector. News RSS/Atom ingestion, conservative cross-source corroboration, and keyword-based catalyst triage are implemented. The EVM JSON-RPC layer provides native wallet balance snapshots, bounded ERC-20 Transfer-log analysis, token metadata/total supply, configured holder-watchlist balances, and cross-chain token/wallet/smart-money intelligence for explicitly configured EVM networks. A private read-only MCP stdio adapter is implemented with tools for the five intended AI clients; actual connection in each owner's account remains unverified until end-to-end tests are performed there. Non-EVM chains, indexed holder distributions, automated historical backfills, validated forecasting/backtesting, and production database operations remain future work. Upstream source code has NOT been copied into this repository; see docs/REPOSITORY_IMPORT_PLAN.md and docs/THIRD_PARTY_NOTICES.md.

## Combined derivatives analysis

A read-only analysis endpoint combines locally stored USD-M price candles, open-interest statistics, and funding events:

```http
GET /api/v1/analysis/derivatives/funding-open-interest/{symbol}?period=1h&price_interval=1h&limit=24
```

The result reports open-interest and price changes, funding-rate context, and cautious co-movement descriptions. It does not infer individual trader positions or label a rise in open interest as a confirmed long or short signal. Data is local-only; collect and store the required series first. The equivalent MCP tool is `analyze_funding_open_interest`.

## Advanced derivatives trend and signal history

The read-only endpoint `GET /api/v1/analysis/derivatives/advanced/{symbol}` evaluates stored USD-M open-interest changes, short-term acceleration, robust MAD-based spike candidates, price/OI divergence candidates, configurable funding-rate extremes, and locally captured force-order context. The configured funding threshold is a user-supplied parameter, not an empirically calibrated universal threshold. Spike detection is withheld when the baseline MAD is zero or insufficient.

Completed snapshots are stored idempotently in `DERIVATIVES_SIGNAL_DATABASE_PATH` and can be read through `GET /api/v1/history/derivatives-signals/{symbol}`. The MCP tools are `analyze_advanced_derivatives` and `get_derivatives_signal_history`. Liquidation context is incomplete: Binance's force-order stream is not a complete liquidation tape, and absence of stored events does not establish that no liquidations occurred. These outputs are descriptive research evidence, not trade instructions.

## Combined derivatives intelligence

`GET /api/v1/analysis/derivatives/combined/{symbol}?period=1h&limit=100` joins locally stored USD-M open-interest, global long/short account ratio and taker buy/sell ratio only where all three have exactly matching timestamps. It reports changes over the common aligned window and shows the latest funding event separately, because funding timestamps do not necessarily match ratio intervals. No missing values are forward-filled or interpolated. At least two exact matches are required. The MCP tool is `analyze_combined_derivatives_intelligence`.

## Stored futures account and taker ratios

Manual collection endpoints store Binance USD-M global long/short account ratio and taker buy/sell ratio observations in a dedicated SQLite database:

- `POST /api/v1/history/derivatives-ratios/USD_M/GLOBAL_LONG_SHORT/BTCUSDT/collect?period=1h&limit=500`
- `POST /api/v1/history/derivatives-ratios/USD_M/TAKER_BUY_SELL/BTCUSDT/collect?period=1h&limit=500`
- `GET /api/v1/history/derivatives-ratios/USD_M/GLOBAL_LONG_SHORT/BTCUSDT?period=1h&limit=200`
- `GET /api/v1/history/derivatives-ratios/USD_M/TAKER_BUY_SELL/BTCUSDT?period=1h&limit=200`

The MCP reader is `get_stored_derivatives_ratio_history`. Storage is idempotent by market, ratio type, symbol, period and timestamp. Collection is manual; it is not automatically scheduled. Global long/short ratio is an account-count ratio, not position size. Taker buy/sell ratio measures aggressive buy/sell volume, not guaranteed future price direction.

## Multi-timeframe derivatives research

The read-only endpoint `GET /api/v1/analysis/derivatives/multi-timeframe/{symbol}?periods=5m,15m,1h,4h,1d&limit=48` combines independently stored USD-M Open Interest and price observations across selected periods. It reports rising/falling/flat OI directions, missing timeframes and a cautious agreement classification. Confirmation is withheld when the latest OI timestamps differ, when any requested timeframe lacks sufficient records, or when only one timeframe is selected. Each completed period analysis writes a local signal snapshot. The MCP tool is `analyze_multi_timeframe_derivatives`.

## Run locally
```bash
python -m venv .venv
pip install -r requirements.txt
uvicorn app.main:app --app-dir backend --reload
```
Open `/docs` for the interactive API documentation. See [personal AI client integration](docs/AI_CLIENT_INTEGRATION.md) for the five-client ChatGPT, Gemini, Manus, Claude, and Perplexity scope, private access, OpenAPI discovery, error handling, and deployment guidance.

## Disclaimer
This software is for research and education. It does not provide guaranteed predictions or financial advice. Crypto assets are volatile; users are responsible for their own decisions.
