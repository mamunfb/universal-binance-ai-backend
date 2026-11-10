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

## What is not claimed

- Not a cross-chain scan. This first adapter supports EVM JSON-RPC only.
- Not a full historical chain indexer; provider retention and log-range limits apply.
- No verified exchange wallet directory is bundled.
- Transfers to an exchange-labeled address are not proof of a deposit, sale, or exchange customer.
- Transfers from a labeled address are not proof of accumulation.
- Whale threshold is token quantity, not USD value.
- Smart-money labels, beneficial ownership, holder distribution, active addresses, and exchange reserves require additional indexed datasets and verified attribution.
- Native token transfers are not included in ERC-20 Transfer logs.
