-- Shared ownership leases for background collector groups.
-- All application replicas must use the same DATABASE_URL for coordination.
CREATE TABLE IF NOT EXISTS public.collector_leases (
    collector_name TEXT PRIMARY KEY,
    owner_token TEXT NOT NULL,
    lease_generation BIGINT NOT NULL DEFAULT 1 CHECK (lease_generation > 0),
    lease_expires_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT collector_leases_name_nonempty CHECK (length(trim(collector_name)) > 0),
    CONSTRAINT collector_leases_owner_nonempty CHECK (length(trim(owner_token)) > 0)
);
CREATE INDEX IF NOT EXISTS idx_collector_leases_expiry
    ON public.collector_leases (lease_expires_at);
