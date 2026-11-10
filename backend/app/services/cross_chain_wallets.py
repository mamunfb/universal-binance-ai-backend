from __future__ import annotations

import asyncio
import json
from typing import Any

from app.providers.evm_rpc import EVMRPCProvider


def parse_chain_rpc_configs(raw: str) -> list[dict[str, Any]]:
    try:
        entries = json.loads(raw or "[]")
    except json.JSONDecodeError as exc:
        raise ValueError("EVM_CHAIN_RPC_URLS must be valid JSON") from exc
    if not isinstance(entries, list):
        raise ValueError("EVM_CHAIN_RPC_URLS must be a JSON array")
    result = []
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Each chain RPC config must be an object")
        chain_id, rpc_url = entry.get("chain_id"), entry.get("rpc_url")
        if isinstance(chain_id, bool) or not isinstance(chain_id, int) or chain_id <= 0:
            raise ValueError("Each chain config requires a positive integer chain_id")
        if chain_id in seen:
            raise ValueError(f"Duplicate chain_id: {chain_id}")
        if not isinstance(rpc_url, str) or not rpc_url.startswith("https://"):
            raise ValueError("Each chain config requires an HTTPS rpc_url")
        seen.add(chain_id)
        result.append({"chain_id": chain_id, "rpc_url": rpc_url,
                       "chain_name": str(entry.get("chain_name") or f"chain-{chain_id}")})
    return result


async def cross_chain_native_wallet_snapshot(configs: list[dict[str, Any]],
                                              addresses: list[str],
                                              timeout_seconds: float = 15.0) -> dict[str, Any]:
    if len(addresses) > 50:
        raise ValueError("At most 50 wallet addresses are supported")
    normalized = []
    for address in addresses:
        if not isinstance(address, str) or len(address) != 42 or not address.startswith("0x"):
            raise ValueError("Invalid EVM wallet address")
        try:
            int(address[2:], 16)
        except ValueError as exc:
            raise ValueError("Invalid hexadecimal EVM wallet address") from exc
        normalized.append(address.lower())

    async def inspect(config: dict[str, Any]) -> dict[str, Any]:
        try:
            provider = EVMRPCProvider(config["rpc_url"], timeout_seconds)
            actual_chain_id = await provider.chain_id()
            if actual_chain_id != config["chain_id"]:
                return {"status": "FAILED", "expected_chain_id": config["chain_id"],
                        "actual_chain_id": actual_chain_id, "chain_name": config["chain_name"],
                        "error": "RPC chain_id does not match configured chain_id"}
            snapshot = await asyncio.gather(
                *(provider.native_balance(address) for address in normalized),
                return_exceptions=True,
            )
            wallets = []
            for address, value in zip(normalized, snapshot):
                if isinstance(value, Exception):
                    wallets.append({"address": address, "status": "FAILED",
                                    "error": f"{type(value).__name__}: {str(value)[:200]}"})
                else:
                    wallets.append({"address": address, "status": "COMPLETED",
                                    "native_balance_wei": str(value),
                                    "native_balance": value / 10**18})
            return {"status": "COMPLETED" if all(w["status"] == "COMPLETED" for w in wallets) else "INCOMPLETE",
                    "chain_id": actual_chain_id, "chain_name": config["chain_name"], "wallets": wallets}
        except Exception as exc:
            return {"status": "FAILED", "chain_id": config["chain_id"],
                    "chain_name": config["chain_name"],
                    "error": f"{type(exc).__name__}: {str(exc)[:250]}"}

    results = await asyncio.gather(*(inspect(config) for config in configs))
    return {
        "status": "COMPLETED" if results and all(item["status"] == "COMPLETED" for item in results) else "INCOMPLETE",
        "chain_count": len(results), "wallet_count": len(normalized),
        "chains": results,
        "identity_warning": "The same EVM address on multiple chains is not proof of the same beneficial owner or entity. Native balances are chain-specific snapshots.",
        "coverage_warning": "Only configured chains and explicitly supplied addresses are queried. No token balances, cross-chain bridges, ownership links, or complete wallet history are inferred.",
    }
