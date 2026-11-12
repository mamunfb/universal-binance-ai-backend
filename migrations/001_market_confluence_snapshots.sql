-- Durable Market Confluence snapshot store (Neon/PostgreSQL)
-- Apply once to the target database before setting DATABASE_URL in production.
CREATE TABLE IF NOT EXISTS public.market_confluence_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    market TEXT NOT NULL CHECK (market IN ('SPOT', 'USD_M', 'COIN_M')),
    symbol TEXT NOT NULL,
    interval TEXT NOT NULL,
    analyzed_at_ms BIGINT NOT NULL CHECK (analyzed_at_ms > 0),
    bias TEXT NOT NULL CHECK (bias IN ('BULLISH', 'BEARISH', 'MIXED', 'UNKNOWN')),
    alignment TEXT NOT NULL,
    reference_price DOUBLE PRECISION,
    reference_close_time_ms BIGINT,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT market_confluence_reference_price_positive
        CHECK (reference_price IS NULL OR reference_price > 0),
    CONSTRAINT market_confluence_reference_close_required
        CHECK (reference_price IS NULL OR reference_close_time_ms IS NOT NULL),
    CONSTRAINT market_confluence_reference_not_future
        CHECK (reference_close_time_ms IS NULL OR reference_close_time_ms <= analyzed_at_ms),
    CONSTRAINT market_confluence_snapshot_unique
        UNIQUE (market, symbol, interval, analyzed_at_ms)
);

CREATE INDEX IF NOT EXISTS idx_market_confluence_history
    ON public.market_confluence_snapshots
    (market, symbol, interval, analyzed_at_ms DESC);
