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
