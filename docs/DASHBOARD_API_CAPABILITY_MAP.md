# Dashboard API & Capability Map

**Baseline:** `main` commit `527afbb3f2aff7c76db32fb3593302e2cc3ccab5`  
**Frontend branch:** `feat/institutional-dashboard-design`  
**Rule:** This document maps observed route definitions only. It does not imply production health or end-to-end success.

## Verified route definitions in the inspected backend source

| Dashboard area | Method and route | Current integration state | Notes |
|---|---|---|---|
| Backend health | GET `/health` | Wired | Process health only; not exchange or database health |
| Spot scanner | GET `/api/v1/markets/spot/scan` | Wired | Optional `quote_asset`; blank UI filter requests all quote assets. Response fields include `eligible_symbols`, `scanned_symbols`, `matched_symbols`, `failed_symbols`, `excluded_pair_counts`, `results`, `unique_coins`, `newly_listed_pairs_30d` |
| USDⓈ-M scanner | GET `/api/v1/markets/futures/usdm/scan` | Wired | Supports optional quote, minimum quote volume and perpetual-only filters |
| COIN-M scanner | GET `/api/v1/markets/futures/coinm/scan` | Wired | Supports optional quote, minimum quote volume and perpetual-only filters |
| Futures combined scan | GET `/api/v1/markets/futures/scan-all` | Available in backend; not yet wired | Scans USDⓈ-M and COIN-M together |
| All-market scan | GET `/api/v1/markets/scan-all` | Available in backend; not yet wired | Verify exact response contract before integration |
| Research preflight | GET `/api/v1/research/preflight` | Wired | Probes Spot/USDⓈ-M/COIN-M public exchange endpoints and configured capabilities |
| Research phase readiness | GET `/api/v1/research/phase-readiness` | Wired | Readiness metadata; not proof all phases are complete |
| Spot klines | GET `/api/v1/markets/spot/klines/{symbol}` | Wired through chart module | Native intervals; response contains `klines` arrays |
| USDⓈ-M klines | GET `/api/v1/markets/futures/usdm/klines/{symbol}` | Wired through chart module | Native intervals; response contains `klines` arrays |
| COIN-M klines | GET `/api/v1/markets/futures/coinm/klines/{symbol}` | Wired through chart module | Native intervals; response contains `klines` arrays |
| Market evidence | GET `/api/v1/analysis/market-evidence/{symbol}` | Wired | Evidence snapshot includes Spot and USD-M context; do not assume selected-market-only output |
| Market data quality | GET `/api/v1/quality/market-data/{market}/{symbol}` | Wired | Quality endpoint has a narrower timeframe enum than the dashboard's full timeframe selector |

## Timeframe handling

The Coin Analysis workspace offers 16 requested timeframes: 1m, 3m, 5m, 15m, 30m, 1h, 2h, 3h, 4h, 6h, 8h, 12h, 1D, 3D, 1W and 1M.

- Native backend kline routes were inspected and accept Binance-native intervals except 3h.
- 3h is currently built in the frontend from 1h OHLCV rows. Only UTC-aligned groups containing exactly three consecutive hourly candles are retained. Incomplete groups are discarded.
- Client-side EMA, SMA, Wilder RSI, MACD line, Bollinger bands, ATR and VWAP are descriptive calculations only; they are not a substitute for validated backend research outputs or a trade signal.
- The backend market-data-quality endpoint currently accepts a smaller interval set and does not accept 3h, 3D, 1W or 1M. The UI must not call that endpoint with unsupported values.

## Designed capabilities not yet verified as end-to-end backend features

These pages are included in the approved design, but their complete UI-to-API data contract has not yet been confirmed:
- Daily scheduled AI research, 15-minute scheduling health and daily summary generation.
- AI candidate ranking, Bullish/Bearish lists and complete coin-selection report.
- Complete/Rolling/Hybrid Historical Research selectors and Neon + R2 federated archive queries.
- Coin comparison across all requested dimensions.
- Full News verification, deduplication and original-source link presentation.
- Complete On-Chain/tokenomics/developer activity provider coverage.
- Unified signal lifecycle, performance and false-signal evaluation across all markets.
- Reports generation/export and archive restore verification.
- Full collector/Neon/R2 operational status aggregation.

These sections are intentionally labelled as planned or capability-not-verified in the UI. Do not enable actions until the backend route, schema, authorization, error model and tests are verified.

## Scanner field mapping

Spot scan `results[]` uses fields such as `symbol`, `base_asset`, `quote_asset`, `last_price`, `price_change_percent_24h`, `quote_volume_24h`, `best_bid`, `best_ask`, `spread_bps` and `status`. The frontend scanner table uses those actual names. The scan also explicitly reports when order-book depth, volume-surge comparison and market-cap enrichment were not collected for every pair.

## Security and integration constraints

- The browser API client sends a Bearer token only when the user enters one in Settings. It is held in page memory only; no localStorage/sessionStorage/cookie persistence is used.
- Remote backend URLs must use HTTPS; HTTP is accepted only for localhost/127.0.0.1 development.
- Requests use `credentials: omit`, `cache: no-store`, timeout/abort handling and JSON response validation.
- API data is rendered as text/JSON, not interpolated as HTML.
- No Binance trading API key, order endpoint, withdrawal endpoint or execution control is included.
- Backend authentication, authorization, CORS, rate limiting and validation remain authoritative. Frontend controls are not a security boundary.

## Required follow-up before production integration

1. Inspect response schemas and tests for each endpoint on the target branch.
2. Verify auth requirements and CORS for the deployed frontend origin.
3. Add frontend automated tests and CI invocation.
4. Implement missing research/archive endpoints in a separate, approved backend branch after this frontend contract is reviewed.
5. Verify the live deployment separately; a successful static build or HTTP health response does not establish full platform readiness.
