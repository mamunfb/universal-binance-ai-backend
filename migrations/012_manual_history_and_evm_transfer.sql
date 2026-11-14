-- PostgreSQL persistence for manually collected derivatives ratios and EVM transfers.
-- Keep the schema aligned with the SQLite store contracts while enabling lease-fenced writes.

CREATE TABLE IF NOT EXISTS public.derivatives_ratio_history (
    market TEXT NOT NULL,
    ratio_type TEXT NOT NULL,
    symbol TEXT NOT NULL,
    period TEXT NOT NULL,
    timestamp_ms BIGINT NOT NULL CHECK (timestamp_ms >= 0),
    payload JSONB NOT NULL,
    source TEXT NOT NULL,
    collected_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (market, ratio_type, symbol, period, timestamp_ms)
);

CREATE INDEX IF NOT EXISTS idx_derivatives_ratio_history_lookup
    ON public.derivatives_ratio_history (market, ratio_type, symbol, period, timestamp_ms);

CREATE TABLE IF NOT EXISTS public.evm_transfer_logs (
    chain_id BIGINT NOT NULL CHECK (chain_id > 0),
    contract_address TEXT NOT NULL,
    transaction_hash TEXT NOT NULL,
    log_index BIGINT NOT NULL CHECK (log_index >= 0),
    block_number BIGINT NOT NULL CHECK (block_number >= 0),
    from_address TEXT NOT NULL,
    to_address TEXT NOT NULL,
    amount_raw TEXT NOT NULL,
    removed BOOLEAN NOT NULL DEFAULT FALSE,
    indexed_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (chain_id, contract_address, transaction_hash, log_index)
);

CREATE INDEX IF NOT EXISTS idx_evm_transfer_contract_block
    ON public.evm_transfer_logs (chain_id, contract_address, block_number);

CREATE TABLE IF NOT EXISTS public.evm_transfer_index_ranges (
    id BIGSERIAL PRIMARY KEY,
    chain_id BIGINT NOT NULL CHECK (chain_id > 0),
    contract_address TEXT NOT NULL,
    from_block BIGINT NOT NULL CHECK (from_block >= 0),
    to_block BIGINT NOT NULL CHECK (to_block >= from_block),
    transfer_count BIGINT NOT NULL CHECK (transfer_count >= 0),
    indexed_at TIMESTAMPTZ NOT NULL,
    UNIQUE (chain_id, contract_address, from_block, to_block)
);

CREATE INDEX IF NOT EXISTS idx_evm_transfer_index_ranges_lookup
    ON public.evm_transfer_index_ranges (chain_id, contract_address, from_block, to_block);
