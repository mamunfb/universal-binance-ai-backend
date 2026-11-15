# Universal Binance AI — Dashboard Design Specification

**Project:** `mamunfb/universal-binance-ai-backend`  
**Document status:** Approved design baseline for frontend implementation  
**Branch:** `feat/institutional-dashboard-design`  
**Design decisions:** Dense information layout; permanently expanded sidebar; advanced multi-panel charts; dark-first theme; responsive desktop/tablet/mobile; research-only, no execution.

## 1. Product intent and non-negotiable boundaries

Build a professional market-intelligence and trading-research terminal for Binance Spot, USDⓈ-M Futures and COIN-M Futures. The dashboard supports complete eligible-market discovery, daily research, historical analysis, coin comparison, risk review and manual trading decisions.

It MUST NOT place orders, manage positions, transfer funds, request withdrawal permissions, or imply guaranteed returns. No Binance trading-permission API key is required. Any credentials used to access the private research backend are entered for the current browser session only and are not persisted in localStorage, sessionStorage, cookies or URLs.

The UI must never fabricate a price, metric, scan count, news item, signal, confidence, timestamp, history record or availability state. Missing or unsupported data is rendered as `UNAVAILABLE`, `UNKNOWN`, `NOT IMPLEMENTED` or `STALE` with a reason where known. Every data view identifies market, symbol, timeframe, source and last-updated time when the API supplies them.

## 2. Approved visual and interaction system

- **Density:** Dense, terminal-style information hierarchy; use compact rows, tables and aligned metric cards without sacrificing legibility.
- **Sidebar:** Expanded by default on desktop and persistently visible; on narrow screens it becomes an accessible drawer. Do not collapse it automatically on desktop.
- **Charts:** Advanced multi-panel chart workspace with price/candles, volume, indicator panes, overlays, crosshair-ready chart adapter and clear empty/error states. Do not draw synthetic price data.
- **Theme:** Dark-first institutional palette. Theme architecture may support a later light theme, but dark mode is the implementation baseline.
- **Layout:** Fixed-width navigation rail plus fluid content canvas; responsive grid; sticky top context bar; scrollable content panels.
- **Typography:** Tabular numerals for prices/counts, clear semantic headings, compact metadata and readable contrast.
- **Status semantics:** Green = verified healthy/positive state, amber = incomplete/warning, red = failed/stale/high risk, neutral = unknown/unavailable. Colour is never the sole carrier of meaning.
- **Accessibility:** Semantic landmarks, keyboard navigation, visible focus, labels for inputs, accessible chart descriptions and reduced-motion support.

## 3. Global application shell

### 3.1 Persistent sidebar navigation

1. Overview
2. Daily AI Research
3. Spot Scanner
4. USDⓈ-M Scanner
5. COIN-M Scanner
6. AI Selected Coins
7. Bullish Candidates
8. Bearish Candidates
9. Coin Analysis
10. Coin Comparison
11. Historical Research
12. Technical Analysis
13. Derivatives Intelligence
14. Order Flow & Liquidity
15. Liquidation Intelligence
16. News & Catalysts
17. On-Chain Intelligence
18. Signals & Performance
19. Risk Monitoring
20. Reports
21. Data Reliability
22. System Settings

Navigation entries may show a capability state: Available, Partial, Planned, or Unavailable. A menu item must not imply an implemented backend endpoint where none exists.

### 3.2 Global top bar

- Market context selector: Spot / USDⓈ-M / COIN-M.
- Global symbol search and quick navigation.
- Global timeframe selector.
- Last successful refresh timestamp and data freshness indicator.
- Backend connection state.
- Manual refresh action with loading and failure feedback.
- User-configured timezone display; default presentation timezone is Asia/Dhaka (UTC+6), with raw UTC timestamps available for traceability.
- No trade execution controls.

### 3.3 Global data-state contract

Every API-backed panel supports: idle, loading, success, empty, partial, stale, unauthorized, rate-limited, server-error and unavailable/not-implemented. Preserve the last successful result when refresh fails, but mark it stale and show the failed refresh time. Never replace failed data with plausible-looking defaults.

## 4. Page specifications

### 4.1 Overview

- Market-wide scan summary by market type: eligible pairs, scanned pairs, successful pairs, failed pairs, excluded/ineligible pairs and coverage percentage only when the backend provides the denominator.
- Scan freshness, duration, API errors, rate-limit events and retry/backoff summary when supplied.
- Daily research status and last completed report.
- AI-selected candidates with market, symbol, rank, evidence status and reason.
- Bullish and bearish candidate lists; no forced candidates.
- Market regime and cross-market context.
- Key derivatives and liquidity indicators with provenance.
- News/catalyst summary with source and published time.
- Historical performance summary with sample size and evaluation caveats.
- System reliability cards for Neon, R2, scanner jobs, collectors and archive integrity. Unknown status remains Unknown.

### 4.2 Market scanners (Spot, USDⓈ-M, COIN-M)

- Complete eligible market discovery; no fixed UI-imposed symbol cap.
- Search, sortable columns, filters, pagination/virtualization that do not silently truncate the scan.
- Pair, base asset, quote asset, market type, trading status, listing/delisting state if available.
- Last price, 24h volume, liquidity/spread/depth and volatility only when supplied.
- Scan coverage panel: eligible, attempted, succeeded, failed, skipped with explicit reasons.
- API error/rate-limit/retry summary.
- Duplicate base-asset grouping and primary-pair rationale if backend supports it.
- Export only data actually returned by the backend; disclose partial coverage.

### 4.3 Daily AI Research

- Daily run timeline and report status.
- Market overview; Spot and Futures opportunities; bullish/bearish candidates.
- Volume, momentum, breakout/breakdown, derivatives, news, risk and historical comparison sections.
- Previous-day signal/performance review.
- Every conclusion links to evidence, source, timestamp and completeness state.
- Clearly distinguish computed metrics, AI interpretation and unavailable evidence.
- Scheduled run cadence target: 15-minute scans (96 per day) and one daily research summary; scheduler configuration/health must come from backend, not frontend timers.

### 4.4 AI Selected Coins / candidate lists

- Candidate ranking without forcing a fixed count.
- Fields: coin, pair, market, price, trend, volume, liquidity, momentum, volatility, indicators, derivatives context, historical comparison, news catalysts, entry zone, invalidation/stop, targets, risk/reward, confidence, selection reason and evidence coverage.
- Confidence must be omitted/unknown unless a validated backend methodology returns it.
- Candidate detail opens Coin Analysis with market, symbol and timeframe context.
- Distinguish research candidates from trade instructions; user makes any manual decision.

### 4.5 Coin Analysis

- Header: asset/pair, market type, trading status, source, last update, data-quality state.
- Timeframes: 1m, 3m, 5m, 15m, 30m, 1h, 2h, 3h, 4h, 6h, 8h, 12h, 1D, 3D, 1W, 1M.
- Popular timeframe shortcuts: 15m, 1h, 4h, 1D, 1W.
- Advanced multi-panel chart: candlesticks, volume, overlays and separate indicator panes. Preserve exact candle timestamps and timezone.
- Indicators: EMA, SMA, RSI, MACD, Bollinger Bands, VWAP, ATR, ADX, Stochastic RSI; Volume Profile only where valid inputs exist.
- Structure: support/resistance, trendline, breakout/breakdown, momentum, divergence, volatility and market structure.
- Changing timeframe must refresh all timeframe-dependent chart, indicator, trend, levels, entry/invalidation and historical-comparison data as one coherent context. Display per-panel freshness if endpoints update independently.
- Binance-native intervals are preferred. For unsupported 3h, aggregate complete 1h candles into 3h buckets, align to UTC bucket boundaries, require complete constituent candles, preserve source timestamps and mark aggregation provenance. Never infer missing candles.
- Entry/stop/target display only when supported by returned analysis; show unavailable otherwise.

### 4.6 Coin Comparison

- Compare selected symbols across the same market and timeframe where possible.
- Side-by-side trend, return, volume, liquidity, volatility, indicators, derivatives, news, historical outcomes and data completeness.
- Disclose non-comparable fields, differing timestamps and different quote pairs.
- No fabricated normalized values.

### 4.7 Historical Research

Three distinct user-selectable modes:
1. **Complete Historical Research:** all retained and archived historical data.
2. **Rolling Historical Research:** configurable recent 6-month or 1-year detailed window.
3. **Hybrid Historical Research:** query hot/important data from Neon and archived data from Cloudflare R2, merged with duplicate detection and provenance.

Each mode shows requested period, actual covered period, row/candle counts, gaps, sources, archive objects, retrieval time, completeness and errors. The UI must not imply the mode works until its backend query/archive integration is implemented and tested. Archive integrity verification and restore testing must pass before any Neon retention deletion.

### 4.8 Technical Analysis

- Multi-timeframe technical summary, indicator values, price structure, levels, volatility and evidence quality.
- Explain indicator settings and calculation timeframe.
- Null/insufficient history shown explicitly.
- Chart overlays and panes can be toggled; no synthetic backfilled values.

### 4.9 Derivatives Intelligence

- Open interest and change, funding rate/history, long/short account ratio, taker buy/sell ratio, basis, futures volume, Spot/Futures divergence, leverage risk.
- Liquidation data and order-book imbalance where available.
- Distinguish account-count ratios from position size; distinguish force-order snapshots from complete liquidation tape.
- Missing series remain unavailable; no interpolation/forward-fill unless the backend explicitly documents and labels it.

### 4.10 Order Flow & Liquidity

- Order-book depth/imbalance, bid/ask liquidity, aggregate trades, taker flow, liquidity sweep and market structure evidence.
- Display capture window, sequence/continuity limitations, freshness and collector health.
- A snapshot is not represented as a complete order-book history.

### 4.11 Liquidation Intelligence

- Recent liquidation observations, clusters and derived levels with coverage caveats.
- Explicitly disclose that force-order stream coverage may be incomplete.
- Absence of events is not proof that no liquidation occurred.

### 4.12 News & Catalysts

- Coin-specific news, official announcements, listing/delisting, unlocks, regulatory, security, partnership and events.
- Headline, publisher/source, published timestamp, original URL, asset mapping, duplicate/corroboration state and verification status.
- Distinguish publication time from retrieval time.
- Unverified/contradictory sources are visibly flagged and must not be presented as confirmed catalysts.

### 4.13 On-Chain Intelligence

- Project background, utility, tokenomics, supply/unlocks, developer activity, ecosystem/network activity, transactions, whale activity and exchange flows.
- Show provider and chain coverage.
- If provider, chain or metric is not configured, show Unavailable; never invent holder distributions or whale movements.

### 4.14 Signals & Performance

- Historical signal timeline, status lifecycle, evaluation horizon, sample size, coverage and outcome.
- Accuracy/precision/recall/confusion matrix only where methodology and denominator are disclosed.
- False-signal analysis, regime breakdown and overlapping-sample caveats.
- Clearly separate historical descriptive evaluation from future predictive certainty.

### 4.15 Risk Monitoring

- Entry zone, invalidation, stop, targets, risk/reward, volatility and liquidity risk when available.
- Position sizing only when user inputs and exchange filters are supplied; otherwise illustrative/unknown.
- Trade-avoidance states and reasons.
- No execution, leverage controls or order submission.

### 4.16 Reports

- Daily summaries, market scan reports, research reports, historical comparison and performance reviews.
- Report metadata: generated time, data cutoff, sources, coverage, mode and limitations.
- Download/export only from persisted or generated report artifacts.

### 4.17 Data Reliability

- Neon primary DB connectivity/status; R2 archive availability, object inventory, integrity verification and restore-test status.
- Scanner run history and 15-minute cadence health.
- Collector runtime, last success/error, lag, missing intervals, retries and rate limits.
- Source-level freshness and coverage.
- Do not expose secrets, DSNs, raw auth headers or sensitive infrastructure details.

### 4.18 System Settings

- Private backend base URL and session-only credential entry.
- API connectivity test and safe logout/clear credentials.
- Display timezone, default market, default timeframe and chart preferences.
- No storage of credentials in browser persistent storage.
- No Binance trade permissions or withdrawal scopes.

## 5. API integration contract

The frontend must maintain a capability registry mapping each page/widget to:
- exact backend endpoint and HTTP method;
- required query/path parameters;
- response schema/version;
- market and timeframe support;
- authentication requirement;
- source/freshness fields;
- known limitations;
- tests and implementation status.

Existing endpoints are integrated only after response shape and auth requirements are verified from backend code/docs/tests. No endpoint is guessed. Planned UI sections may be scaffolded but must be labelled Planned/Unavailable until a real API exists.

Current route inventory includes existing health, research preflight/phase readiness, Spot/Futures market scans, Spot/Futures klines, technical/multi-timeframe analysis, market evidence, market structure confluence, order flow/order book, liquidity and liquidation analysis, derivatives, historical stores, news, EVM/on-chain and market-data quality routes. Exact route/parameter contracts must be maintained in the API mapping document.

## 6. Architecture and frontend implementation constraints

- Frontend remains a separate static application under `dashboard/`; backend Python files, database migrations, workflows, secrets and deployment configuration are out of scope for this frontend branch.
- Prefer dependency-light static frontend unless a separately reviewed build system is introduced.
- Separate modules/components by shell, navigation, API client, capability registry, page renderers, charts, formatting and state.
- Central API client: timeout/abort, safe JSON parsing, auth errors, rate limits, request cancellation, retry only for safe idempotent GETs with bounded backoff.
- Avoid unsafe `innerHTML` for API/user-controlled strings; use DOM text APIs or strict escaping.
- No hard-coded prices, sample market values or fake status badges.
- No browser persistence for credentials.
- Chart library must be reviewed for licence, bundle size, maintenance, accessibility and data-volume behaviour before adoption.
- No telemetry or third-party analytics that leak private market/research data by default.

## 7. Data and timezone conventions

- API timestamps are preserved as supplied; render in configured timezone (default Asia/Dhaka) and provide UTC traceability.
- Market type and quote pair are always visible where ambiguity is possible.
- Custom 3h aggregation requires full aligned 1h constituents; partial buckets are marked incomplete and excluded from indicator calculations that require complete bars.
- Distinguish exchange event time, collection time, analysis time and report generation time.

## 8. Security and operational policy

- Public source code does not imply public database access.
- No credentials in source, HTML, logs, URLs, screenshots or exported reports.
- Browser talks only to configured private backend over HTTPS in deployed environments.
- Backend remains responsible for authentication, authorization, rate limiting, validation and CORS; frontend checks are not a security boundary.
- No trading/order/withdrawal endpoints or controls.
- Never delete historical data based on a frontend action.

## 9. Acceptance criteria

The design is accepted when:
1. Every requested domain is represented in the navigation/page map.
2. Every page has a defined purpose, data fields, source/provenance and unavailable-state behaviour.
3. All 16 timeframes are specified, including strict 3h aggregation rules.
4. All three historical research modes are specified with archive safety constraints.
5. Scanner coverage and failures cannot be hidden by UI caps.
6. Dark dense layout, expanded desktop sidebar and advanced multi-panel chart workspace are implemented responsively.
7. No fabricated data, guaranteed-return language, auto-trading, order placement or withdrawal capability exists.
8. Existing backend capabilities are mapped to exact verified APIs; gaps are labelled rather than disguised.
9. Frontend tests cover API client, formatting, navigation, state transitions, XSS-safe rendering, timeframe selection and responsive/accessibility basics.
10. No backend source/config/database/workflow file is changed in this frontend branch.

## 10. Implementation sequence

1. Establish the separate frontend branch from the inspected main baseline.
2. Commit this specification and API/capability map.
3. Implement the dashboard shell, navigation, overview, scanner and coin-analysis workspace.
4. Add page scaffolds for remaining domains with explicit capability status.
5. Integrate only verified existing APIs.
6. Add frontend tests and static validation.
7. Produce a frontend-only PR; do not merge or deploy without approval.
8. After frontend design/API contract is stable, perform a separate backend gap analysis. Backend changes require a separate approved implementation branch and tests.

## 11. Baseline repository note

The inspected `main` baseline contains an existing `dashboard/index.html` and substantial FastAPI route coverage. The current route contracts must be rechecked against the exact branch commit before integration. The tracked prompt/document inventory should also be reconciled with the user's canonical Master Prompt 01 and Master Prompt 02 before declaring phase-level compliance. This specification does not supersede either canonical prompt.
