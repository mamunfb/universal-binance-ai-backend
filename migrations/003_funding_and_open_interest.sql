-- Binance USD-M funding history and open-interest statistics.
-- Apply before enabling the corresponding PostgreSQL storage adapters.
CREATE TABLE IF NOT EXISTS public.historical_funding_rates (
    market TEXT NOT NULL CHECK (market = 'USD_M'),
    symbol TEXT NOT NULL,
    funding_time_ms BIGINT NOT NULL CHECK (funding_time_ms >= 0),
    funding_rate DOUBLE PRECISION NOT NULL,
    mark_price DOUBLE PRECISION CHECK (mark_price IS NULL OR mark_price > 0),
    source TEXT NOT NULL,
    collected_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (market, symbol, funding_time_ms)
);

CREATE INDEX IF NOT EXISTS idx_funding_history_lookup
    ON public.historical_funding_rates (market, symbol, funding_time_ms DESC);

CREATE TABLE IF NOT EXISTS public.historical_open_interest (
    market TEXT NOT NULL CHECK (market = 'USD_M'),
    symbol TEXT NOT NULL,
    period TEXT NOT NULL CHECK (period IN ('5m', '15m', '30m', '1h', '2h', '4h', '6h', '12h', '1d')),
    timestamp_ms BIGINT NOT NULL CHECK (timestamp_ms >= 0),
    sum_open_interest DOUBLE PRECISION NOT NULL CHECK (sum_open_interest >= 0),
    sum_open_interest_value DOUBLE PRECISION NOT NULL CHECK (sum_open_interest_value >= 0),
    cmc_circulating_supply DOUBLE PRECISION CHECK (cmc_circulating_supply IS NULL OR cmc_circulating_supply >= 0),
    source TEXT NOT NULL,
    collected_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (market, symbol, period, timestamp_ms)
);

CREATE INDEX IF NOT EXISTS idx_open_interest_lookup
    ON public.historical_open_interest (market, symbol, period, timestamp_ms DESC);
