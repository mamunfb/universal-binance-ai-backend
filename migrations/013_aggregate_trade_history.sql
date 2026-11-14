-- PostgreSQL persistence for Binance aggregate trades.
-- The collector's lease-fenced INSERT and all readers use this shared table.

CREATE TABLE IF NOT EXISTS public.aggregate_trades (
    market TEXT NOT NULL,
    symbol TEXT NOT NULL,
    trade_id BIGINT NOT NULL CHECK (trade_id >= 0),
    event_time_ms BIGINT NOT NULL CHECK (event_time_ms >= 0),
    trade_time_ms BIGINT NOT NULL CHECK (trade_time_ms >= 0),
    price DOUBLE PRECISION NOT NULL CHECK (price > 0 AND price <> 'Infinity'::DOUBLE PRECISION AND price <> 'NaN'::DOUBLE PRECISION),
    quantity DOUBLE PRECISION NOT NULL CHECK (quantity > 0 AND quantity <> 'Infinity'::DOUBLE PRECISION AND quantity <> 'NaN'::DOUBLE PRECISION),
    notional DOUBLE PRECISION NOT NULL CHECK (notional > 0 AND notional <> 'Infinity'::DOUBLE PRECISION AND notional <> 'NaN'::DOUBLE PRECISION),
    buyer_is_maker BOOLEAN NOT NULL,
    aggressor_side TEXT NOT NULL CHECK (aggressor_side IN ('BUY', 'SELL')),
    raw_payload JSONB NOT NULL,
    PRIMARY KEY (market, symbol, trade_id)
);

CREATE INDEX IF NOT EXISTS idx_aggregate_trades_market_symbol_time
    ON public.aggregate_trades (market, symbol, trade_time_ms DESC, trade_id DESC);
