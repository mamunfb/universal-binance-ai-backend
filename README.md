# Universal Binance AI Backend

A research-only backend for collecting public cryptocurrency market data, computing transparent technical indicators, and exposing structured analysis data to AI clients.

## Project goals
- Scan eligible Binance Spot, USDⓈ-M Futures, and COIN-M Futures markets where public endpoints support the requested data.
- Normalize market data and report coverage, timestamps, failures, and missing fields.
- Provide technical indicators and multi-timeframe market context.
- Add news, on-chain, derivatives, and tokenomics providers only after source and license review.
- Expose a stable REST API first; add MCP and AI-client adapters after the core API is tested.
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
- Multi-timeframe Spot analysis (15m/1h/4h/1d) and a limited BTC/ETH market context endpoint.
- Optional Binance USDⓈ-M force-order WebSocket snapshot collector with SQLite persistence; disabled by default and explicitly documented as incomplete snapshot coverage.
- Spot pivot-based support/resistance clusters and Fibonacci retracement/extension levels.
- Anchored VWAP, OHLCV-approximated Volume Profile (POC/VAH/VAL), and rule-based BOS/CHoCH/liquidity-sweep candidates.

Futures coverage is based on exchangeInfo symbols marked TRADING and the selected quote asset. Scanner responses include coverage counts and data failures. See docs/FUTURES_API.md, docs/DERIVATIVES_API.md, docs/MULTI_TIMEFRAME_API.md, and docs/LIQUIDATION_COLLECTOR.md, and docs/PRICE_LEVELS_API.md, and docs/VOLUME_STRUCTURE_API.md.

## Repository layout
- backend/ — API and application services
- providers/ — exchange and external data-source adapters
- analysis/ — indicators, screening, validation, and risk calculations
- integrations/ — AI client adapters
- mcp-server/ — future Model Context Protocol server
- docs/ — architecture, source inventory, and operating rules
- tests/ — automated tests

## Upstream source projects
Upstream projects will be evaluated and integrated individually. They will not be blindly copied into this repository. Each source must have its license, maintenance status, security posture, and relevance reviewed first. See docs/REPOSITORY_IMPORT_PLAN.md.

## Current status
The repository now includes Spot and Futures scanners/klines, Spot technical indicators, USDⓈ-M derivatives snapshots, multi-timeframe Spot analysis, a limited BTC/ETH context endpoint, and an opt-in liquidation snapshot collector. News intelligence, on-chain data, validated forecasting/backtesting, production database operations, and AI/MCP adapters remain future work. Upstream source code has NOT been copied into this repository; see docs/REPOSITORY_IMPORT_PLAN.md and docs/THIRD_PARTY_NOTICES.md.

## Run locally
```bash
python -m venv .venv
pip install -r requirements.txt
uvicorn app.main:app --app-dir backend --reload
```
Open `/docs` for the interactive API documentation.

## Disclaimer
This software is for research and education. It does not provide guaranteed predictions or financial advice. Crypto assets are volatile; users are responsible for their own decisions.
