# On-Chain Intelligence — EVM RPC first stage

## Standard API error responses

The API returns a consistent JSON envelope for HTTP errors and request validation failures:

```json
{
  "status": "FAILED",
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "The request could not be validated.",
    "details": {
      "reason": "to_block must be >= from_block"
    }
  }
}
```

The `error.code` is intended for client branching; `error.message` is a safe summary; optional `error.details` contains structured validation locations or endpoint-provided reasons. Validation details omit submitted input values. Unexpected server exceptions return a generic `INTERNAL_SERVER_ERROR` message and do not expose internal exception text. HTTP status codes remain unchanged. Successful response schemas are unaffected.

## Configuration

Configure an HTTPS JSON-RPC endpoint for an EVM-compatible chain using EVM_RPC_URL and EVM_CHAIN_NAME. Use a provider and plan whose terms permit your intended request volume. Never put private keys in this application; only read-only JSON-RPC methods are used.

## Endpoints

### Wallet native-balance snapshot

GET /api/v1/onchain/evm/wallets?addresses=0x...,0x...

Returns chain ID, block number, and native-asset balances for supplied EVM addresses. It does not identify owners or prove that an address is a whale/smart-money wallet.

### ERC-20 transfer activity

GET /api/v1/onchain/evm/token/{contract}/activity?from_block=...&to_block=...&decimals=18&whale_threshold_tokens=100000

Reads ERC-20 Transfer event logs for one contract and bounded block interval. The maximum range is capped to protect RPC capacity. Decimals must be supplied by the caller; it is not guessed. Whale threshold is in token units, not USD.

Optional EVM_EXCHANGE_ADDRESSES uses comma-separated Label=0xAddress entries. Only manually configured addresses are counted in exchange flow.

### Token supply and tracked holder watchlist

GET /api/v1/onchain/evm/token/{contract}/snapshot?addresses=0x...,0x...

Reads ERC-20 name, symbol, decimals, total supply, and balances for supplied addresses plus configured exchange addresses. Reports each tracked address's share of total supply and the combined tracked share. Maximum 50 addresses. This is a watchlist snapshot, not complete holder distribution or top-holder discovery.

## What is not claimed

- Not a cross-chain scan. This first adapter supports EVM JSON-RPC only.
- Not a full historical chain indexer; provider retention and log-range limits apply.
- No verified exchange wallet directory is bundled.
- Transfers to an exchange-labeled address are not proof of a deposit, sale, or exchange customer.
- Transfers from a labeled address are not proof of accumulation.
- Whale threshold is token quantity, not USD value.
- Smart-money labels, beneficial ownership, holder distribution, active addresses, and exchange reserves require additional indexed datasets and verified attribution.
- Native token transfers are not included in ERC-20 Transfer logs.

### Persistent ERC-20 transfer history

POST /api/v1/onchain/evm/token/{contract}/index

JSON body:
```json
{"from_block": 1000000, "to_block": 1001000, "chunk_size": 500}
```

Indexes a caller-selected block range in bounded chunks and stores normalized Transfer logs in SQLite. Replaying the same range is idempotent by chain ID, contract, transaction hash, and log index. Successful chunks are recorded individually. If an RPC request fails, the response reports the last completed range and next block to retry; retrying from that block is safe.

GET /api/v1/onchain/evm/token/{contract}/history?from_block=...&to_block=...&limit=500

Returns stored transfers and the successful indexed ranges recorded for that chain and contract. An empty result is not proof of no transfers unless the requested range is covered.

Configuration:
- `EVM_TRANSFER_DATABASE_PATH=data/evm_transfers.sqlite3`
- `EVM_INDEX_MAX_TOTAL_BLOCKS=10000`

The request range is capped by EVM_INDEX_MAX_TOTAL_BLOCKS, and each chunk is capped at 2000 blocks. SQLite storage is local to the running instance; ephemeral hosting filesystems may lose it on restart or redeploy. Use a persistent disk or external database for production history retention.

GET /api/v1/onchain/evm/token/{contract}/history/flows?from_block=...&to_block=...&decimals=18&limit=50

Aggregates sender/receiver flows from locally indexed logs, returning the highest net receivers and senders. Amounts are calculated from raw integer token units before conversion. This is an address-flow view for stored records, not a holder-balance ranking, owner attribution, or complete chain view unless indexed coverage spans the requested range.

### Evidence-backed wallet attribution registry

GET /api/v1/onchain/evm/wallet-registry

Returns the operator-maintained registry for the currently configured EVM chain. Optional lookup:

GET /api/v1/onchain/evm/wallet-registry?addresses=0x...,0x...

Configuration uses `EVM_WALLET_REGISTRY`, a JSON array. Example (replace the illustrative values with reviewed evidence before use):

```json
[
  {
    "address": "0x1111111111111111111111111111111111111111",
    "label": "exchange",
    "entity_name": "Example Exchange",
    "verification_status": "pending_review",
    "evidence_url": "https://example.org/address-disclosure",
    "evidence_note": "Describe exactly what the cited disclosure supports",
    "source_published_at": "2026-01-01",
    "last_reviewed_at": "2026-11-10"
  }
]
```

Allowed labels: exchange, fund, market_maker, protocol_treasury, smart_money, whale, unknown. Allowed statuses: unverified, pending_review, verified, rejected. Entries marked verified must include an HTTPS evidence URL and a non-empty evidence note. The application validates provenance fields but does not independently authenticate the source. Never mark a wallet verified solely because it sends tokens to an exchange or has a large balance. Do not add guessed addresses or unreferenced social-media claims.

The registry endpoint is read-only. Populate it through controlled deployment configuration; do not expose public write access for attribution labels. No exchange or smart-money wallet list is bundled by default.

The historical `/history/flows` response also attaches matching registry attribution to each listed address. Missing registry matches are explicitly returned as `unknown` / `unverified`; this is not an automated smart-money classifier.

### Verified smart-money token activity

GET /api/v1/onchain/evm/token/{contract}/smart-money?from_block=...&to_block=...&decimals=18&limit=100

Summarizes sent, received, net token flow, transaction count, and first/last activity block for addresses explicitly labeled `smart_money` with `verification_status=verified` in EVM_WALLET_REGISTRY. Unverified or pending-review wallets are excluded. The response includes indexed range coverage and returns INCOMPLETE if any part of the requested block interval is not covered. This is observed token transfer activity, not evidence of trade direction, portfolio holdings, profitability, or future price movement.

The smart-money activity response also includes `cohort_summary`: counts of verified wallets with net inflow/outflow/neutral flow, the combined net token flow, and the addresses in each directional group. This is a descriptive cohort aggregation over the selected block interval; it does not establish coordinated behavior or intent. Wallet-level rows are still limited by the requested response limit, while cohort counts and address groups are calculated over all matching verified wallets.

The smart-money endpoint accepts optional `window_blocks` (default 1000) and returns `accumulation_trend`. Each populated window reports net transfer flow for verified smart_money registry wallets, with direction labeled NET_INFLOW or NET_OUTFLOW and cumulative net flow from the requested starting block. Transfers between two wallets in the verified cohort cancel at cohort level and do not create net flow. Empty/zero-net windows are omitted. Cumulative flow is a flow sum initialized at zero, not an opening balance, wallet holdings, or proof of purchase/sale. Always inspect the top-level coverage object; incomplete ranges may omit activity.

### Verified wallet token concentration snapshot

GET /api/v1/onchain/evm/token/{contract}/concentration

Reads the ERC-20 total supply and balances for verified addresses in the operator registry, then groups the observed balances by registry label (for example `smart_money`, `exchange`, `fund`). The response includes the pinned snapshot block, optional block timestamp and age, per-group balance and percentage of total supply, plus failed balance calls. Token metadata, supply, and all tracked balances are read at the same explicit block tag. If the RPC cannot return block metadata, the snapshot remains usable while timestamp-derived freshness is marked unavailable. Only up to 50 registry addresses are supported by the existing snapshot service. This is not a full holder ranking or complete token concentration metric.

### Cross-chain native wallet snapshots

GET /api/v1/onchain/evm/cross-chain/wallets?addresses=0x...,0x...

Configure `EVM_CHAIN_RPC_URLS` as a JSON array, for example:
`[{"chain_id":1,"chain_name":"Ethereum","rpc_url":"https://YOUR_ETHEREUM_RPC"},{"chain_id":56,"chain_name":"BNB Smart Chain","rpc_url":"https://YOUR_BSC_RPC"}]`

The service verifies each endpoint's reported chain ID against configuration before querying native balances for supplied addresses. Each chain is reported independently; a failed or mismatched RPC does not invalidate successful results from other chains, but overall status becomes INCOMPLETE. At most 50 addresses are accepted. This endpoint does not establish that matching addresses have the same owner, does not query ERC-20 balances, and does not infer bridge relationships or cross-chain transactions. Keep provider URLs and API credentials private; do not commit real credentials.


### Cross-chain ERC-20 token snapshots

GET /api/v1/onchain/evm/cross-chain/token/{asset_id}?addresses=0x...,0x...

Configure `EVM_CHAIN_TOKEN_CONTRACTS` as a JSON array. Each entry defines one chain-specific contract and an operator-assigned grouping key:

```json
[
  {"chain_id":1,"chain_name":"Ethereum","asset_id":"usd-coin","contract_address":"0x...","rpc_url":"https://YOUR_ETHEREUM_RPC"},
  {"chain_id":56,"chain_name":"BNB Smart Chain","asset_id":"usd-coin","contract_address":"0x...","rpc_url":"https://YOUR_BSC_RPC"}
]
```

The endpoint validates each RPC's reported chain ID, reads token name/symbol/decimals/total supply, and queries balances for 1–50 supplied wallet addresses. It first reads the current block number and pins all ERC-20 `eth_call` requests for that chain to that block tag. Chain results are independent; any failed chain or wallet makes the overall status INCOMPLETE. The same asset_id is an operator-defined grouping label only: it does not prove that contracts are issued by the same entity, redeemable 1:1, or economically equivalent. Verify token contracts and bridge/issuer provenance before comparing supplies or balances. This is not a full holder ranking, transaction history, or ownership analysis. Use HTTPS RPC URLs and keep provider credentials private.


### Cross-chain indexed ERC-20 flow intelligence

GET /api/v1/onchain/evm/cross-chain/token/{asset_id}/flows?from_block=...&to_block=...&decimals=18&limit=50

Uses the chain-specific contracts configured in `EVM_CHAIN_TOKEN_CONTRACTS` and aggregates locally indexed ERC-20 Transfer logs independently for each chain. Returns top net receivers/senders, requested block range, and indexed coverage gaps per chain. The overall response is INCOMPLETE if any configured chain has a coverage gap or RPC chain-ID mismatch. Index each chain/contract range first with the existing per-chain history index endpoint. The `decimals` query parameter is applied to every contract selected by the asset_id; only group contracts with matching decimals, or the displayed token quantities will be wrong. The endpoint does not fetch missing logs automatically and does not infer cross-chain transfers, wallet ownership, or token equivalence. A net transfer flow is not a wallet balance or proof of buying/selling.


### Cross-chain verified wallet cohort flows

GET /api/v1/onchain/evm/cross-chain/token/{asset_id}/smart-money?from_block=...&to_block=...&decimals=18&limit=50&window_blocks=1000

Combines locally indexed ERC-20 transfer flows for the configured contracts under an asset_id, separately by chain, and filters wallet activity to operator-registry entries labeled `smart_money` with `verification_status=verified`. Other labels (including fund, market_maker, protocol_treasury, and whale) are not included in this specific cohort. Entries pending review, unverified, rejected, or labeled exchange/unknown are excluded. The response reports per-chain coverage and becomes INCOMPLETE if any selected chain has missing indexed blocks. Configure registry entries with the matching chain_id and evidence for that chain; do not assume the same address is the same entity on every chain. The service does not independently authenticate registry evidence. The decimals parameter is applied to all selected contracts and must be correct and consistent.

Each chain also returns `accumulation_trend`, grouped into block windows controlled by `window_blocks` (default 1000; allowed 1–1,000,000). Window direction is labeled NET_INFLOW or NET_OUTFLOW based on cohort-level net transfer flow. Transfers between two verified cohort wallets offset each other. Only windows with non-zero cohort net flow are returned. `cumulative_net_flow` starts at zero at the requested from_block; it is a cumulative transfer-flow sum, not a balance, holdings estimate, or proof of buying/selling. Trend reliability depends on complete indexed coverage; inspect each chain’s coverage before interpreting it. Activity and cohort net flow are not trading intent, profitability, or a price forecast.


### Unified cross-chain indexed intelligence

GET /api/v1/onchain/evm/cross-chain/token/{asset_id}/intelligence?from_block=100&to_block=200&decimals=18&limit=50&window_blocks=1000

Combines the existing per-chain indexed address-flow summary and verified smart-money cohort transfer-flow trend into one response. Each chain retains its own status, contract address, indexed coverage, and underlying data. Missing cohort results and incomplete indexed coverage do not count as complete. The endpoint is read-only and does not index missing history.

This endpoint deliberately does **not** claim live wallet balances, holder concentration, exchange trade intent, or a unified cross-chain block timeline. Configure EVM_CHAIN_TOKEN_CONTRACTS and EVM_WALLET_REGISTRY, and index the requested ERC-20 log ranges first. The supplied decimals must match each selected contract.

The unified intelligence response also includes `verified_entity_flows`, grouped by verified registry labels such as `exchange`, `fund`, `market_maker`, `protocol_treasury`, `smart_money`, and `whale`. It reports gross sent/received and net received token flow from locally indexed logs. Unverified registry entries are excluded. Same-label internal transfers cancel in the cohort net, although they remain represented in gross sent/received totals. Exchange-labeled flow is not proof of exchange deposits, withdrawals, customer activity, or executed trades.

The unified response's `verified_wallet_concentration` section now queries balances for verified registry wallets at one pinned block per chain. It groups successful balances by registry label and reports token amounts and each cohort's share of total supply. It is intentionally limited to at most 50 verified addresses per chain; if the registry exceeds this limit, the API reports an incomplete concentration result rather than silently sampling the first 50. An empty verified registry is reported as `EMPTY`. This remains a tracked-wallet snapshot, not a full holder ranking, and balances on different chains are observed at different chain-specific block heights.

### Unified intelligence data quality metadata

The unified endpoint also exposes an AI-facing top-level `data_quality` envelope. It contains:
- `status`: the overall COMPLETE/INCOMPLETE result status
- `coverage`: per-chain completion and indexed-coverage counts, plus the requested block range
- `freshness`: per-chain balance snapshot block aliases, optional block timestamp/time/age, and counts of snapshots with or without timestamp metadata
- `limitations`: explicit boundaries on what the dataset can establish
- `interpretation_notes`: guidance for treating incomplete, empty, or timestamp-unavailable results

The original `data_quality_summary` remains available for backward compatibility. A missing timestamp means freshness is unknown; it does not mean that a snapshot is stale. The envelope does not infer coverage or freshness beyond the returned chain-level observations.


The unified endpoint now returns a top-level `data_quality_summary` with counts of completed/incomplete chains, chains with complete indexed ERC-20 coverage, chains with complete smart-money coverage, and chains with successful balance snapshots. Each chain includes a `data_quality` object with coverage-gap counts, snapshot block and canonical block-number alias, optional block timestamp, timestamp status, UTC block time and age, successful/failed wallet balance counts, verified registry wallet count, and chain result status. It also includes `component_status` for indexed address flows, verified smart-money flows, verified entity flows, and verified wallet concentration, plus `incomplete_reasons` listing the specific unavailable, incomplete, or uncovered components. The balance snapshot freshness fields mirror `verified_wallet_concentration`; timestamp-derived values are null when the RPC cannot provide block metadata.

A chain is marked `COMPLETED` only when the component requests succeed and both indexed-flow and smart-money coverage explicitly report complete. Missing coverage metadata is treated conservatively as unconfirmed and keeps the chain `INCOMPLETE`. A completed result does not certify registry identity, full holder coverage, or investment conclusions. Age is measured against the chain block timestamp at API response time and does not establish finality or market-data validity.


### Snapshot block time and freshness

Cross-chain tracked-wallet balance snapshots (native and ERC-20) include the
pinned `snapshot_block` and canonical `snapshot_block_number` alias, plus
`snapshot_block_timestamp` (Unix seconds), `snapshot_timestamp_status`,
`snapshot_block_time` (UTC ISO-8601), and `snapshot_age_seconds` when the RPC
returns block metadata. ERC-20 snapshots also expose `snapshot_block_tag` for
the exact EVM block tag used by all token calls. Age is measured at API response time against the on-chain
block timestamp; it is not the exact RPC query completion time. If the RPC cannot
provide a timestamp, balances remain usable and timestamp fields are null with
status `UNAVAILABLE`. Freshness age is not itself a guarantee of market-data
validity or chain finality.


Native wallet snapshots (single-chain and cross-chain) are pinned to an explicit
block number. Responses expose the canonical `snapshot_block` and
`snapshot_block_number` aliases, `snapshot_block_timestamp`,
`snapshot_timestamp_status`, `snapshot_block_time`, and
`snapshot_age_seconds`. Existing single-chain native-wallet keys
(`block_number`, `block_timestamp`, `timestamp_status`, and `block_time`)
remain available for backward compatibility. If timestamp lookup fails, the
balance snapshot is retained and timestamp status is `UNAVAILABLE`. This
prevents a response from mixing balances read at different moving `latest`
blocks within the same snapshot.

Standalone ERC-20 token snapshots also pin total supply, metadata, and every
tracked-wallet balance call to one explicit block. Responses expose the canonical
`snapshot_block` and `snapshot_block_number` aliases, the exact
`snapshot_block_tag`, and optional timestamp-derived freshness fields.
Single-chain concentration responses preserve the same block aliases.
Timestamp lookup failure does not discard successfully retrieved block-pinned
token data.


### API error responses and request tracing

API errors use a stable JSON envelope with `status: "FAILED"` and an `error` object containing a machine-readable `code` and safe `message`. Validation errors include structured `details` without echoing submitted input values. Explicit HTTP errors preserve their HTTP status and structured details where supplied; unexpected server errors return a generic message and do not expose exception text.

Every response includes an `X-Request-ID` response header containing a server-generated request identifier. Error response bodies also include the same identifier as `request_id`, allowing clients to correlate a reported failure with server-side logs. The identifier is generated by the API; clients should quote it when reporting an issue. It is not an authentication token or a guarantee that server logs are retained.
