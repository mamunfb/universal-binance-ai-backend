-- Reproducible USD-M derivatives analysis snapshots.
CREATE TABLE IF NOT EXISTS public.derivatives_signal_snapshots (
    market TEXT NOT NULL CHECK (market = 'USD_M'),
    symbol TEXT NOT NULL,
    period TEXT NOT NULL CHECK (period IN ('5m', '15m', '30m', '1h', '2h', '4h', '6h', '12h', '1d')),
    end_time_ms BIGINT NOT NULL CHECK (end_time_ms >= 0),
    generated_at TIMESTAMPTZ NOT NULL,
    payload JSONB NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    PRIMARY KEY (market, symbol, period, end_time_ms)
);
CREATE INDEX IF NOT EXISTS idx_derivatives_signal_history
    ON public.derivatives_signal_snapshots (market, symbol, period, end_time_ms DESC);
