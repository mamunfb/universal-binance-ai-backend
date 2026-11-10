from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timezone
from typing import Any

from app.providers.evm_rpc import EVMRPCProvider

_ASSET_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")


def _validate_address(address: str) -> None:
    if not isinstance(address, str) or len(address) != 42 or not address.startswith("0x"):
        raise ValueError("Expected a 20-byte 0x-prefixed EVM address")
    try:
        int(address[2:], 16)
    except ValueError as exc:
        raise ValueError("Invalid hexadecimal EVM address") from exc


def parse_chain_token_configs(raw: str) -> list[dict[str, Any]]:
    try:
        entries = json.loads(raw or "[]")
    except json.JSONDecodeError as exc:
        raise ValueError("EVM_CHAIN_TOKEN_CONTRACTS must be valid JSON") from exc
    if not isinstance(entries, list):
        raise ValueError("EVM_CHAIN_TOKEN_CONTRACTS must be a JSON array")
    parsed = []
    seen: set[tuple[int, str]] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Each chain token config must be an object")
        chain_id = entry.get("chain_id")
        asset_id = entry.get("asset_id")
        contract = entry.get("contract_address")
        rpc_url = entry.get("rpc_url")
        if isinstance(chain_id, bool) or not isinstance(chain_id, int) or chain_id <= 0:
            raise ValueError("Each token config requires a positive integer chain_id")
        if not isinstance(asset_id, str) or not _ASSET_ID.fullmatch(asset_id.lower()):
            raise ValueError("Each token config requires a simple asset_id")
        if not isinstance(rpc_url, str) or not rpc_url.startswith("https://"):
            raise ValueError("Each token config requires an HTTPS rpc_url")
        _validate_address(contract)
        key = (chain_id, asset_id.lower())
        if key in seen:
            raise ValueError(f"Duplicate asset_id for chain_id: {chain_id}/{asset_id}")
        seen.add(key)
        parsed.append({
            "chain_id": chain_id, "asset_id": asset_id.lower(),
            "contract_address": contract.lower(), "rpc_url": rpc_url,
            "chain_name": str(entry.get("chain_name") or f"chain-{chain_id}"),
        })
    return parsed


def _uint(result: str) -> int:
    if not isinstance(result, str) or not result.startswith("0x"):
        raise ValueError("Invalid ABI uint result")
    return int(result, 16)


def _text(result: str) -> str | None:
    if not isinstance(result, str) or not result.startswith("0x"):
        return None
    try:
        raw = bytes.fromhex(result[2:])
        if len(raw) < 32:
            return None
        offset = int.from_bytes(raw[:32], "big")
        if offset + 32 <= len(raw):
            length = int.from_bytes(raw[offset:offset + 32], "big")
            if offset + 32 + length <= len(raw):
                return raw[offset + 32:offset + 32 + length].decode("utf-8")
        return raw[:32].rstrip(b"\\x00").decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None


async def _token_on_chain(config: dict[str, Any], addresses: list[str],
                          timeout_seconds: float) -> dict[str, Any]:
    provider = EVMRPCProvider(config["rpc_url"], timeout_seconds)
    actual_chain_id = await provider.chain_id()
    if actual_chain_id != config["chain_id"]:
        return {"status": "FAILED", "chain_id": actual_chain_id,
                "expected_chain_id": config["chain_id"], "chain_name": config["chain_name"],
                "asset_id": config["asset_id"],
                "error": "RPC chain_id does not match configured chain_id"}
    block = await provider.block_number()
    try:
        block_timestamp = await provider.block_timestamp(block)
        timestamp_status = "AVAILABLE"
    except Exception:
        # Preserve usable block-pinned balances when an RPC omits block metadata.
        block_timestamp = None
        timestamp_status = "UNAVAILABLE"
    tag = hex(block)
    contract = config["contract_address"]
    total_supply, decimals, symbol, name = await asyncio.gather(
        provider.eth_call(contract, "0x18160ddd", tag),
        provider.eth_call(contract, "0x313ce567", tag),
        provider.eth_call(contract, "0x95d89b41", tag),
        provider.eth_call(contract, "0x06fdde03", tag),
    )
    supply_raw, decimals_value = _uint(total_supply), _uint(decimals)
    if decimals_value > 36:
        raise ValueError("Token decimals outside supported range 0..36")

    async def balance(address: str) -> dict[str, Any]:
        data = "0x70a08231" + address[2:].rjust(64, "0")
        try:
            raw = _uint(await provider.eth_call(contract, data, tag))
            return {"address": address, "status": "COMPLETED",
                    "balance_raw": str(raw), "balance_tokens": raw / (10 ** decimals_value),
                    "share_of_total_supply_pct": raw / supply_raw * 100 if supply_raw else None}
        except Exception as exc:
            return {"address": address, "status": "FAILED",
                    "error": f"{type(exc).__name__}: {str(exc)[:200]}"}

    wallets = await asyncio.gather(*(balance(address) for address in addresses))
    ok = [row for row in wallets if row["status"] == "COMPLETED"]
    tracked_raw = sum(int(row["balance_raw"]) for row in ok)
    return {
        "status": "COMPLETED" if len(ok) == len(wallets) else "INCOMPLETE",
        "asset_id": config["asset_id"], "chain_id": actual_chain_id,
        "chain_name": config["chain_name"], "contract_address": contract,
        "snapshot_block": block, "snapshot_block_tag": tag,
        "snapshot_block_timestamp": block_timestamp,
        "snapshot_timestamp_status": timestamp_status,
        "token": {"name": _text(name), "symbol": _text(symbol), "decimals": decimals_value,
                  "total_supply_raw": str(supply_raw),
                  "total_supply_tokens": supply_raw / (10 ** decimals_value)},
        "wallet_count": len(addresses), "wallets": wallets,
        "tracked_combined_balance_raw": str(tracked_raw),
        "tracked_combined_balance_tokens": tracked_raw / (10 ** decimals_value),
        "tracked_combined_supply_share_pct": tracked_raw / supply_raw * 100 if supply_raw else None,
    }


async def cross_chain_erc20_snapshot(configs: list[dict[str, Any]], asset_id: str,
                                     addresses: list[str], timeout_seconds: float = 15.0) -> dict[str, Any]:
    if not _ASSET_ID.fullmatch(asset_id.lower()):
        raise ValueError("Invalid asset_id")
    if not 1 <= len(addresses) <= 50:
        raise ValueError("Provide between 1 and 50 wallet addresses")
    normalized = []
    for address in addresses:
        _validate_address(address)
        normalized.append(address.lower())
    selected = [item for item in configs if item["asset_id"] == asset_id.lower()]
    if not selected:
        raise ValueError(f"No configured token contracts for asset_id '{asset_id}'")
    async def inspect(config: dict[str, Any]) -> dict[str, Any]:
        try:
            return await _token_on_chain(config, normalized, timeout_seconds)
        except Exception as exc:
            return {"status": "FAILED", "chain_id": config["chain_id"],
                    "chain_name": config["chain_name"], "asset_id": config["asset_id"],
                    "contract_address": config["contract_address"],
                    "error": f"{type(exc).__name__}: {str(exc)[:250]}"}
    chains = await asyncio.gather(*(inspect(item) for item in selected))
    return {
        "status": "COMPLETED" if chains and all(item["status"] == "COMPLETED" for item in chains) else "INCOMPLETE",
        "asset_id": asset_id.lower(), "chain_count": len(chains),
        "wallet_count": len(normalized), "chains": chains,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "interpretation_warning": "asset_id is an operator-defined grouping label, not proof that contracts represent economically equivalent or redeemable assets. Verify issuer, bridge, and contract provenance independently.",
        "coverage_warning": "Only configured contracts and explicitly supplied addresses are queried. This is not a full holder ranking, complete supply distribution, transaction history, or cross-chain ownership analysis.",
    }
