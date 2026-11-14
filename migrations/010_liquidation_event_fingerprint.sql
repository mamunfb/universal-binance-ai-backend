-- Add idempotent persistence for exact repeated Binance force-order payloads.
-- Existing rows are retained with NULL fingerprints; no historical rows are deleted or rewritten.
ALTER TABLE public.liquidation_events
    ADD COLUMN IF NOT EXISTS event_fingerprint TEXT;

-- PostgreSQL permits multiple NULL values in a unique index, so legacy rows remain valid.
CREATE UNIQUE INDEX IF NOT EXISTS uq_liquidation_events_event_fingerprint
    ON public.liquidation_events (event_fingerprint);
