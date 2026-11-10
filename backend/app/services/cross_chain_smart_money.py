from __future__ import annotations

import asyncio
from typing import Any

from app.providers.evm_rpc import EVMRPCProvider
from app.services.wallet_attribution import load_wallet_registry


SMART_LABELS = {"smart_money"}


async def cross_chain_verified_wallet_flows(
    configs: list[dict[str, Any]], asset_id: str, from_block: int, to_block: int,
    decimals: int, registry_raw: str, store: Any, timeout_seconds: float = 15.0,
    limit: int = 50, window_blocks: int = 1000,
) -> dict[str, Any]:
    if from_block < 0 or to_block < from_block:
        raise ValueError("Invalid block range")
    if not 0 <= decimals <= 36:
        raise ValueError("decimals must be between 0 and 36")
    if not 1 <= limit <= 200:
        raise ValueError("limit must be between 1 and 200")
    if not 1 <= window_blocks <= 1_000_000:
        raise ValueError("window_blocks must be between 1 and 1000000")
    selected = [item for item in configs if item["asset_id"] == asset_id.lower()]
    if not selected:
        raise ValueError(f"No configured token contracts for asset_id '{asset_id}'")

    async def inspect(config: dict[str, Any]) -> dict[str, Any]:
        try:
            provider = EVMRPCProvider(config["rpc_url"], timeout_seconds)
            chain_id = await provider.chain_id()
            if chain_id != config["chain_id"]:
                return {"status": "FAILED", "chain_id": chain_id,
                        "expected_chain_id": config["chain_id"],
                        "error": "RPC chain_id does not match configured chain_id"}
            registry = load_wallet_registry(registry_raw, chain_id)
            verified_registry = {
                **registry,
                "wallets": [item for item in registry.get("wallets", [])
                            if item["verification_status"] == "verified"
                            and item["label"] in SMART_LABELS],
            }
            coverage = store.range_coverage(chain_id, config["contract_address"],
                                             from_block, to_block)
            flows = store.smart_money_activity(
                chain_id, config["contract_address"], from_block, to_block,
                decimals, verified_registry, limit,
            )
            trend = store.smart_money_accumulation_trend(
                chain_id, config["contract_address"], from_block, to_block,
                decimals, verified_registry, window_blocks,
            )
            return {
                "status": "COMPLETED" if coverage["complete"] else "INCOMPLETE",
                "chain_id": chain_id, "chain_name": config["chain_name"],
                "contract_address": config["contract_address"],
                "coverage": coverage, "verified_wallet_flow": flows,
                "accumulation_trend": trend,
                "verified_registry_wallet_count": len(verified_registry["wallets"]),
            }
        except Exception as exc:
            return {"status": "FAILED", "chain_id": config["chain_id"],
                    "chain_name": config["chain_name"],
                    "error": "SMART_MONEY_ANALYSIS_UNAVAILABLE",
                    "error_type": type(exc).__name__}

    chains = await asyncio.gather(*(inspect(config) for config in selected))
    complete = bool(chains) and all(item["status"] == "COMPLETED" for item in chains)
    return {
        "status": "COMPLETED" if complete else "INCOMPLETE",
        "asset_id": asset_id.lower(), "requested_range": {"from": from_block, "to": to_block},
        "decimals_used": decimals, "chain_count": len(chains), "chains": chains,
        "warning": "Only operator-supplied registry entries marked verified and labeled smart_money are included. Registry verification is not independently authenticated by this service. Cross-chain matching of the same address does not prove common ownership or coordinated intent. Results depend on complete local ERC-20 log coverage and the supplied decimals.",
    }
