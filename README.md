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
Initial repository setup. Upstream repositories have NOT yet been imported. Next: implement the minimal backend skeleton, then integrate approved dependencies with their licenses preserved.

## Disclaimer
This software is for research and education. It does not provide guaranteed predictions or financial advice. Crypto assets are volatile; users are responsible for their own decisions.
