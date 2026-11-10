# On-Chain Intelligence — EVM RPC first stage

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

The smart-money endpoint accepts optional `window_blocks` (default 1000) and returns `accumulation_trend`. Each populated window reports net transfer flow for verified smart_money registry wallets and cumulative net flow from the requested starting block. Empty windows are omitted. Cumulative flow is a flow sum initialized at zero, not an opening balance, wallet holdings, or proof of purchase/sale. Always inspect the top-level coverage object; incomplete ranges may omit activity.

### Verified wallet token concentration snapshot

GET /api/v1/onchain/evm/token/{contract}/concentration

Reads the ERC-20 total supply and balances for verified addresses in the operator registry, then groups the observed balances by registry label (for example `smart_money`, `exchange`, `fund`). The response includes a block number observed before balance calls begin, snapshot time, per-group balance and percentage of total supply, plus failed balance calls. The underlying RPC calls use the provider's latest-state `eth_call`; unless the provider supports a pinned block tag in a future implementation, balances are not guaranteed to be from one atomic block snapshot. Only up to 50 registry addresses are supported by the existing snapshot service. This is not a full holder ranking or complete token concentration metric.

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

GET /api/v1/onchain/evm/cross-chain/token/{asset_id}/smart-money?from_block=...&to_block=...&decimals=18&limit=50

Combines locally indexed ERC-20 transfer flows for the configured contracts under an asset_id, separately by chain, and filters wallet activity using the operator registry for each chain. Included labels are verified entries with labels smart_money, fund, market_maker, protocol_treasury, or whale. Entries pending review, unverified, rejected, or labeled exchange/unknown are excluded. The response reports per-chain coverage and becomes INCOMPLETE if any selected chain has missing indexed blocks. Configure registry entries with the matching chain_id and evidence for that chain; do not assume the same address is the same entity on every chain. The service does not independently authenticate registry evidence. The decimals parameter is applied to all selected contracts and must be correct and consistent. Activity and cohort net flow are transfer-flow summaries, not wallet holdings, trading intent, profitability, or a price forecast.
