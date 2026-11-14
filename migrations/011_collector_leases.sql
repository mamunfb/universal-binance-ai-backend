-- Coordination primitive only. Collectors remain disabled until every persistence path
-- validates the lease row and fencing token inside the same write transaction.
CREATE TABLE IF NOT EXISTS public.collector_leases (
    lease_name TEXT PRIMARY KEY,
    owner_id UUID NOT NULL,
    fencing_token BIGINT NOT NULL CHECK (fencing_token > 0),
    lease_expires_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE INDEX IF NOT EXISTS idx_collector_leases_expiry
    ON public.collector_leases (lease_expires_at);
