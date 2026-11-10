from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from app.providers.evm_rpc import EVMRPCProvider


def _topic_address(topic: str) -> str | None:
    if not isinstance(topic, str) or len(topic) != 66:
        return None
    return "0x" + topic[-40:].lower()


def _hex_int(value: Any) -> int:
    if not isinstance(value, str) or not value.startswith("0x"):
        raise ValueError("Expected hex-encoded integer")
    return int(value, 16)


async def analyze_erc20_activity(provider: EVMRPCProvider, contract: str, from_block: int,
                                 to_block: int, decimals: int,
                                 exchange_addresses: dict[str, str] | None = None,
                                 whale_threshold_tokens: float = 100_000,
                                 max_block_span: int = 2000) -> dict[str, Any]:
    if not 0 <= decimals <= 36:
        raise ValueError("decimals must be between 0 and 36")
    if whale_threshold_tokens < 0:
        raise ValueError("whale_threshold_tokens cannot be negative")
    logs = await provider.token_transfer_logs(
        contract, from_block, to_block, max_block_span=max_block_span
    )
    labels = {address.lower(): name for name, address in (exchange_addresses or {}).items()}
    transfers: list[dict[str, Any]] = []
    total_raw = whale_count = exchange_in_raw = exchange_out_raw = 0
    exchange_flows: dict[str, dict[str, float]] = {}
    for log in logs:
        topics = log.get("topics") or []
        if len(topics) < 3:
            continue
        sender, recipient = _topic_address(topics[1]), _topic_address(topics[2])
        if not sender or not recipient:
            continue
        raw_value = _hex_int(log.get("data"))
        amount = raw_value / (10 ** decimals)
        total_raw += raw_value
        is_whale = amount >= whale_threshold_tokens
        whale_count += int(is_whale)
        from_exchange, to_exchange = labels.get(sender), labels.get(recipient)
        if to_exchange:
            exchange_in_raw += raw_value
            exchange_flows.setdefault(to_exchange, {"inflow": 0.0, "outflow": 0.0})["inflow"] += amount
        if from_exchange:
            exchange_out_raw += raw_value
            exchange_flows.setdefault(from_exchange, {"inflow": 0.0, "outflow": 0.0})["outflow"] += amount
        transfers.append({
            "transaction_hash": log.get("transactionHash"),
            "block_number": _hex_int(log["blockNumber"]) if log.get("blockNumber") else None,
            "log_index": _hex_int(log["logIndex"]) if log.get("logIndex") else None,
            "from_address": sender, "to_address": recipient,
            "amount_raw": str(raw_value), "amount_tokens": amount,
            "whale_candidate": is_whale,
            "from_exchange_label": from_exchange, "to_exchange_label": to_exchange,
        })
    scale = 10 ** decimals
    return {
        "status": "COMPLETED", "generated_at": datetime.now(timezone.utc).isoformat(),
        "contract_address": contract.lower(), "block_range": {"from": from_block, "to": to_block},
        "decimals": decimals, "transfer_count": len(transfers),
        "total_transfer_volume_tokens": total_raw / scale, "whale_candidate_count": whale_count,
        "exchange_flow": {
            "configured_labeled_address_count": len(labels),
            "inflow_tokens": exchange_in_raw / scale, "outflow_tokens": exchange_out_raw / scale,
            "netflow_tokens": (exchange_in_raw - exchange_out_raw) / scale,
            "by_exchange": exchange_flows,
            "interpretation_warning": "Transfers to/from configured addresses do not prove sales or accumulation.",
        },
        "transfers": transfers,
        "limitations": [
            "Whale threshold is token quantity, not USD value.",
            "Address labels are operator-configured and not independently verified.",
            "ERC-20 logs exclude native transfers and non-EVM chains.",
            "A transfer does not prove beneficial ownership, sale, deposit, or accumulation.",
        ],
    }


async def get_evm_wallet_snapshot(provider: EVMRPCProvider, addresses: list[str]) -> dict[str, Any]:
    chain_id, block = await provider.chain_id(), await provider.block_number()
    balances = []
    for address in addresses:
        try:
            balance = await provider.native_balance(address)
            balances.append({"address": address.lower(), "native_balance_wei": str(balance),
                             "native_balance": balance / 10**18, "status": "COMPLETED"})
        except Exception as exc:
            balances.append({"address": address.lower(), "status": "FAILED",
                             "error": f"{type(exc).__name__}: {str(exc)[:250]}"})
    return {
        "status": "COMPLETED" if balances and all(x["status"] == "COMPLETED" for x in balances) else "INCOMPLETE",
        "generated_at": datetime.now(timezone.utc).isoformat(), "chain_id": chain_id,
        "block_number": block, "wallet_count": len(addresses), "wallets": balances,
        "warning": "Native balances are snapshots; they do not identify owners or smart-money wallets.",
    }
