from __future__ import annotations

from typing import Any


def build_phase_readiness(*, news_feed_count: int, onchain_configured: bool) -> dict[str, Any]:
    """Static code-capability map; it does not claim that any live phase has been executed."""
    phases = [
        (1, "Complete market scanner", "INCOMPLETE", "All returned eligible symbols can be enumerated, but all-pair depth, volume surge, market-cap enrichment and complete risk-tag coverage are missing."),
        (2, "Global crypto news intelligence", "BLOCKED" if news_feed_count == 0 else "INCOMPLETE", "RSS/Atom feeds only; no general web search, complete per-coin source sweep or full-name alias registry."),
        (3, "News verification and catalyst analysis", "INCOMPLETE", "Cross-domain title matching and keyword triage exist; primary-claim adjudication, semantic duplicate detection and weighted 0-100 catalyst evidence are not complete."),
        (4, "Initial coin filtering", "PARTIAL", "Basic market eligibility and volume filtering exist; the full documented multi-factor funnel and rejection ledger are not integrated."),
        (5, "Bitcoin and global market analysis", "INCOMPLETE", "BTC condition analysis exists; dominance, total market cap, macro calendar and all external sentiment indices are not integrated."),
        (6, "Deep technical analysis", "PARTIAL", "EMA/SMA, RSI, MACD, Bollinger, support/resistance, Fibonacci, VWAP and volume profile exist; all requested patterns and every timeframe are not in one completed pipeline."),
        (7, "Liquidity and derivatives analysis", "PARTIAL", "Order-book, spread, funding, OI, basis and liquidation components exist; full all-candidate depth and complete execution-cost enrichment are missing."),
        (8, "On-chain intelligence", "PARTIAL" if onchain_configured else "BLOCKED", "EVM-based RPC/token activity only when configured; not universal multi-chain coverage."),
        (9, "Tokenomics and fundamentals", "BLOCKED", "No complete project fundamentals, tokenomics, unlock and competitor-data provider pipeline is present."),
        (10, "Whale and smart-money tracking", "PARTIAL" if onchain_configured else "BLOCKED", "Configured EVM address/transfer evidence exists; broad attribution and wallet identity verification are not established."),
        (11, "Exchange fund-flow analysis", "PARTIAL" if onchain_configured else "BLOCKED", "Configured address flow can be summarized; exchange-wide reserves and complete exchange labels are not established."),
        (12, "Market manipulation detection", "PARTIAL", "Some liquidity/order-flow anomaly evidence exists; this is not comprehensive manipulation proof or a validated detector."),
        (13, "Multi-timeframe confirmation", "PARTIAL", "Multi-timeframe technical/derivatives analyses exist, but no complete candidate-to-final-signal gate is wired."),
        (14, "Historical performance validation", "PARTIAL", "Stored-snapshot observational evaluation and statistical reliability tools exist; this is not a complete execution-aware strategy backtest for both markets."),
        (15, "AI probability and forecasting", "BLOCKED", "No validated predictive model supporting forward statistical probabilities is established; probability must remain NOT ESTABLISHED."),
        (16, "Risk, position planning and timing", "PARTIAL", "User-input Spot/linear USD-M risk arithmetic and signal lifecycle validation exist; COIN-M inverse sizing, liquidation tiers and live entry validation are missing."),
        (17, "Final selection and ranking", "BLOCKED", "No complete cross-candidate weighted ranking and portfolio correlation engine is wired."),
        (18, "Independent AI red-team review", "BLOCKED", "No independent red-team execution workflow is implemented in the backend."),
        (19, "Final signal audit", "BLOCKED", "No complete live recheck/expiry/invalidation audit workflow is wired."),
        (20, "Final professional report", "BLOCKED", "No end-to-end 20-phase report orchestrator is implemented."),
    ]
    return {
        "status": "INCOMPLETE",
        "execution_claim": False,
        "phase_count": 20,
        "completed_phase_count": 0,
        "phases": [
            {"phase_number": number, "phase_name": name, "readiness": status, "gap": gap}
            for number, name, status, gap in phases
        ],
        "important_rule": "Readiness describes code capability only. It is not evidence that a phase was run or that live data was retrieved.",
    }
