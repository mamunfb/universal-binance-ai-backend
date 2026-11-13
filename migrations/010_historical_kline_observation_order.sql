-- Request-observation ordering for mutable historical candles.
-- Existing rows remain NULL (unknown observation order); the first write using
-- the new collector path may refresh them. New writes always carry a token.
ALTER TABLE public.historical_klines
    ADD COLUMN IF NOT EXISTS observation_started_at_ns BIGINT
    CHECK (observation_started_at_ns IS NULL OR observation_started_at_ns >= 0);
