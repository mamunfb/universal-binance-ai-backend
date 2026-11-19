-- Historical OHLCV candles for Spot, USD-M and COIN-M.
-- The application supports PostgreSQL/Neon when DATABASE_URL (or
-- HISTORICAL_KLINE_DATABASE_URL) is configured, and SQLite for local
-- development/tests. Apply this migration before enabling PostgreSQL storage.
CREATE TABLE IF NOT EXISTS public.historical_klines (
    market TEXT NOT NULL CHECK (market IN ('SPOT', 'USD_M', 'COIN_M')),
    symbol TEXT NOT NULL,
    interval TEXT NOT NULL,
    open_time_ms BIGINT NOT NULL CHECK (open_time_ms >= 0),
    open DOUBLE PRECISION NOT NULL CHECK (open > 0),
    high DOUBLE PRECISION NOT NULL CHECK (high > 0),
    low DOUBLE PRECISION NOT NULL CHECK (low > 0),
    close DOUBLE PRECISION NOT NULL CHECK (close > 0),
    volume DOUBLE PRECISION NOT NULL CHECK (volume >= 0),
    close_time_ms BIGINT NOT NULL CHECK (close_time_ms >= open_time_ms),
    quote_volume DOUBLE PRECISION NOT NULL CHECK (quote_volume >= 0),
    trade_count BIGINT NOT NULL CHECK (trade_count >= 0),
    taker_buy_base_volume DOUBLE PRECISION NOT NULL CHECK (taker_buy_base_volume >= 0),
    taker_buy_quote_volume DOUBLE PRECISION NOT NULL CHECK (taker_buy_quote_volume >= 0),
    source TEXT NOT NULL,
    collected_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (market, symbol, interval, open_time_ms),
    CONSTRAINT historical_klines_taker_volume_bound
        CHECK (taker_buy_base_volume <= volume + GREATEST(1e-12, volume * 1e-9)),
    CONSTRAINT historical_klines_ohlc_consistency
        CHECK (high >= GREATEST(open, close, low) AND low <= LEAST(open, close, high))
);

CREATE INDEX IF NOT EXISTS idx_historical_klines_lookup
    ON public.historical_klines (market, symbol, interval, open_time_ms DESC);
