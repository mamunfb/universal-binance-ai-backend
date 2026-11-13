-- Monotonic fencing generation for collector lease takeovers.
-- Existing lease rows begin at generation 1; each new owner increments it.
ALTER TABLE public.collector_leases
    ADD COLUMN IF NOT EXISTS lease_generation BIGINT NOT NULL DEFAULT 1
    CHECK (lease_generation > 0);
