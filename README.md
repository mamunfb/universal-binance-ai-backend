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
The repository includes Spot and Futures scanners/klines, a validated local historical OHLCV store for manually collected Spot/USD-M/COIN-M candles with UTC-aligned gap and coverage inspection, Spot technical indicators, USDⓈ-M derivatives snapshots, Spot/Futures basis and funding comparison, a unified research-only Market Evidence Snapshot, multi-timeframe Spot analysis, a limited BTC/ETH context endpoint, and an opt-in liquidation snapshot collector. News RSS/Atom ingestion, conservative cross-source corroboration, and keyword-based catalyst triage are implemented. The EVM JSON-RPC layer provides native wallet balance snapshots, bounded ERC-20 Transfer-log analysis, token metadata/total supply, configured holder-watchlist balances, and cross-chain token/wallet/smart-money intelligence for explicitly configured EVM networks. A private read-only MCP stdio adapter is implemented with tools for the five intended AI clients; actual connection in each owner's account remains unverified until end-to-end tests are performed there. Non-EVM chains, indexed holder distributions, automated historical backfills, funding/open-interest history storage, validated forecasting/backtesting, and production database operations remain future work. Upstream source code has NOT been copied into this repository; see docs/REPOSITORY_IMPORT_PLAN.md and docs/THIRD_PARTY_NOTICES.md.

## Run locally
```bash
python -m venv .venv
pip install -r requirements.txt
uvicorn app.main:app --app-dir backend --reload
```
Open `/docs` for the interactive API documentation. See [personal AI client integration](docs/AI_CLIENT_INTEGRATION.md) for the five-client ChatGPT, Gemini, Manus, Claude, and Perplexity scope, private access, OpenAPI discovery, error handling, and deployment guidance.

## Disclaimer
This software is for research and education. It does not provide guaranteed predictions or financial advice. Crypto assets are volatile; users are responsible for their own decisions.
