-- USD-M global account and taker buy/sell ratio history.
CREATE TABLE IF NOT EXISTS public.derivatives_ratio_history (
    market TEXT NOT NULL CHECK (market = 'USD_M'),
    ratio_type TEXT NOT NULL CHECK (ratio_type IN ('GLOBAL_LONG_SHORT', 'TAKER_BUY_SELL')),
    symbol TEXT NOT NULL,
    period TEXT NOT NULL CHECK (period IN ('5m', '15m', '30m', '1h', '2h', '4h', '6h', '12h', '1d')),
    timestamp_ms BIGINT NOT NULL CHECK (timestamp_ms >= 0),
    payload JSONB NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    source TEXT NOT NULL,
    collected_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (market, ratio_type, symbol, period, timestamp_ms)
);
CREATE INDEX IF NOT EXISTS idx_derivatives_ratio_history_lookup
    ON public.derivatives_ratio_history (market, ratio_type, symbol, period, timestamp_ms DESC);
