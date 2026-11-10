from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Any
from app.providers.evm_rpc import EVMRPCProvider, TRANSFER_TOPIC


def _validate_evm_address(address: str) -> None:
    if not isinstance(address, str) or len(address) != 42 or not address.startswith("0x"):
        raise ValueError("Expected a 20-byte 0x-prefixed EVM address")
    try:
        int(address[2:], 16)
    except ValueError as exc:
        raise ValueError("Invalid hexadecimal EVM address") from exc


def _topic_address(topic: str) -> str | None:
    if not isinstance(topic, str) or len(topic) != 66 or not topic.startswith("0x"):
        return None
    try:
        int(topic[2:], 16)
    except ValueError:
        return None
    if topic[2:26] != "0" * 24:
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
    _validate_evm_address(contract)
    if isinstance(decimals, bool) or not isinstance(decimals, int) or not 0 <= decimals <= 36:
        raise ValueError("decimals must be an integer between 0 and 36")
    if (isinstance(whale_threshold_tokens, bool) or
            not isinstance(whale_threshold_tokens, (int, float)) or
            not math.isfinite(whale_threshold_tokens) or whale_threshold_tokens < 0):
        raise ValueError("whale_threshold_tokens must be a finite non-negative number")
    if from_block < 0 or to_block < from_block:
        raise ValueError("Invalid block range")
    if to_block - from_block + 1 > max_block_span:
        raise ValueError(f"Block range exceeds configured maximum of {max_block_span}")
    logs = await provider.token_transfer_logs(
        contract, from_block, to_block, max_block_span=max_block_span
    )
    labels = {address.lower(): name for name, address in (exchange_addresses or {}).items()}
    transfers: list[dict[str, Any]] = []
    address_activity: dict[str, dict[str, int]] = {}
    total_raw = whale_count = exchange_in_raw = exchange_out_raw = 0
    exchange_flows: dict[str, dict[str, float]] = {}
    malformed_log_count = 0
    for log in logs:
        if not isinstance(log, dict):
            malformed_log_count += 1
            continue
        topics = log.get("topics")
        if (not isinstance(topics, list) or len(topics) != 3 or
                topics[0] != "0x" + TRANSFER_TOPIC[2:].lower()):
            malformed_log_count += 1
            continue
        sender, recipient = _topic_address(topics[1]), _topic_address(topics[2])
        if not sender or not recipient:
            malformed_log_count += 1
            continue
        try:
            data = log.get("data")
            if not isinstance(data, str) or len(data) != 66:
                raise ValueError("Transfer data must be a 32-byte hex word")
            raw_value = _hex_int(data)
            block_number = _hex_int(log["blockNumber"]) if log.get("blockNumber") is not None else None
            log_index = _hex_int(log["logIndex"]) if log.get("logIndex") is not None else None
        except (KeyError, TypeError, ValueError):
            malformed_log_count += 1
            continue
        amount = raw_value / (10 ** decimals)
        total_raw += raw_value
        address_activity.setdefault(sender, {"sent_raw": 0, "received_raw": 0, "transfer_count": 0})["sent_raw"] += raw_value
        address_activity.setdefault(recipient, {"sent_raw": 0, "received_raw": 0, "transfer_count": 0})["received_raw"] += raw_value
        address_activity[sender]["transfer_count"] += 1
        address_activity[recipient]["transfer_count"] += 1
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
            "block_number": block_number,
            "log_index": log_index,
            "from_address": sender, "to_address": recipient,
            "amount_raw": str(raw_value), "amount_tokens": amount,
            "whale_candidate": is_whale,
            "from_exchange_label": from_exchange, "to_exchange_label": to_exchange,
        })
    scale = 10 ** decimals
    return {
        "status": "INCOMPLETE" if malformed_log_count else "COMPLETED",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "contract_address": contract.lower(), "block_range": {"from": from_block, "to": to_block},
        "decimals": decimals, "transfer_count": len(transfers),
        "malformed_log_count": malformed_log_count,
        "total_transfer_volume_tokens": total_raw / scale, "whale_candidate_count": whale_count,
        "exchange_flow": {
            "configured_labeled_address_count": len(labels),
            "inflow_tokens": exchange_in_raw / scale, "outflow_tokens": exchange_out_raw / scale,
            "netflow_tokens": (exchange_in_raw - exchange_out_raw) / scale,
            "by_exchange": exchange_flows,
            "interpretation_warning": "Transfers to/from configured addresses do not prove sales or accumulation.",
        },
        "address_activity_in_requested_block_range": sorted([
            {"address": address, "sent_tokens": values["sent_raw"] / scale,
             "received_tokens": values["received_raw"] / scale,
             "net_received_tokens": (values["received_raw"] - values["sent_raw"]) / scale,
             "transfer_count": values["transfer_count"]}
            for address, values in address_activity.items()
        ], key=lambda row: abs(row["net_received_tokens"]), reverse=True),
        "transfers": transfers,
        "limitations": [
            "Address activity is limited to the requested block range; it is not a holder ranking or full balance snapshot.",
            "Whale threshold is token quantity, not USD value.",
            "Address labels are operator-configured and not independently verified.",
            "ERC-20 logs exclude native transfers and non-EVM chains.",
            "A transfer does not prove beneficial ownership, sale, deposit, or accumulation.",
        ],
    }


async def get_evm_wallet_snapshot(provider: EVMRPCProvider, addresses: list[str]) -> dict[str, Any]:
    if not isinstance(addresses, list):
        raise ValueError("addresses must be a list of EVM wallet addresses")
    for address in addresses:
        _validate_evm_address(address)
    chain_id, block = await provider.chain_id(), await provider.block_number()
    try:
        block_timestamp = await provider.block_timestamp(block)
        timestamp_status = "AVAILABLE"
    except Exception:
        block_timestamp = None
        timestamp_status = "UNAVAILABLE"
    balances = []
    for address in addresses:
        try:
            balance = await provider.native_balance(address, hex(block))
            balances.append({"address": address.lower(), "native_balance_wei": str(balance),
                             "native_balance": balance / 10**18, "status": "COMPLETED"})
        except Exception as exc:
            balances.append({"address": address.lower(), "status": "FAILED",
                             "error": "BALANCE_UNAVAILABLE",
                             "error_type": type(exc).__name__})
    return {
        "status": "COMPLETED" if balances and all(x["status"] == "COMPLETED" for x in balances) else "INCOMPLETE",
        "generated_at": datetime.now(timezone.utc).isoformat(), "chain_id": chain_id,
        "block_number": block,
        "snapshot_block": block,
        "snapshot_block_number": block,
        "block_timestamp": block_timestamp,
        "snapshot_block_timestamp": block_timestamp,
        "timestamp_status": timestamp_status,
        "snapshot_timestamp_status": timestamp_status,
        "block_time": (
            datetime.fromtimestamp(block_timestamp, timezone.utc).isoformat()
            if block_timestamp is not None else None
        ),
        "snapshot_block_time": (
            datetime.fromtimestamp(block_timestamp, timezone.utc).isoformat()
            if block_timestamp is not None else None
        ),
        "snapshot_age_seconds": (
            max(0, int(datetime.now(timezone.utc).timestamp()) - block_timestamp)
            if block_timestamp is not None else None
        ),
        "wallet_count": len(addresses), "wallets": balances,
        "warning": "Native balances are snapshots; they do not identify owners or smart-money wallets.",
    }

def _decode_abi_uint(value: str) -> int:
    if not isinstance(value, str) or not value.startswith("0x") or len(value) != 66:
        raise ValueError("ABI uint result must be exactly 32 bytes of hex")
    try:
        return int(value[2:], 16)
    except ValueError as exc:
        raise ValueError("ABI uint result contains invalid hexadecimal data") from exc


def _decode_abi_text(value: str) -> str | None:
    if not isinstance(value, str) or not value.startswith("0x"):
        return None
    encoded = value[2:]
    if len(encoded) % 2:
        return None
    try:
        raw = bytes.fromhex(encoded)
    except ValueError:
        return None
    if len(raw) < 32:
        return None

    # Dynamic ABI string: offset word, length word, then UTF-8 bytes.
    offset = int.from_bytes(raw[:32], "big")
    if offset >= 32 and offset % 32 == 0 and offset + 32 <= len(raw):
        length = int.from_bytes(raw[offset:offset + 32], "big")
        start, end = offset + 32, offset + 32 + length
        if end <= len(raw):
            try:
                return raw[start:end].decode("utf-8")
            except UnicodeDecodeError:
                return None

    # Some tokens return bytes32 for name/symbol rather than a dynamic string.
    if len(raw) == 32:
        try:
            return raw.split(b"\x00", 1)[0].decode("utf-8")
        except UnicodeDecodeError:
            return None
    return None


async def get_erc20_token_snapshot(provider: EVMRPCProvider, contract: str,
                                  watch_addresses: dict[str, str]) -> dict[str, Any]:
    _validate_evm_address(contract)
    if not isinstance(watch_addresses, dict):
        raise ValueError("watch_addresses must be a mapping of labels to EVM addresses")
    if len(watch_addresses) > 50:
        raise ValueError("At most 50 tracked addresses are supported per request")
    for label, address in watch_addresses.items():
        if not isinstance(label, str) or not label.strip():
            raise ValueError("Tracked address labels must be non-empty strings")
        _validate_evm_address(address)
    block = await provider.block_number()
    try:
        block_timestamp = await provider.block_timestamp(block)
        timestamp_status = "AVAILABLE"
    except Exception:
        block_timestamp = None
        timestamp_status = "UNAVAILABLE"
    block_tag = hex(block)
    total_raw = _decode_abi_uint(await provider.eth_call(contract, "0x18160ddd", block_tag))
    decimals = _decode_abi_uint(await provider.eth_call(contract, "0x313ce567", block_tag))
    if decimals > 36:
        raise ValueError("Token decimals outside supported range 0..36")
    symbol = _decode_abi_text(await provider.eth_call(contract, "0x95d89b41", block_tag))
    name = _decode_abi_text(await provider.eth_call(contract, "0x06fdde03", block_tag))
    scale = 10 ** decimals
    holders = []
    for label, address in watch_addresses.items():
        data = "0x70a08231" + address[2:].lower().rjust(64, "0")
        try:
            raw = _decode_abi_uint(await provider.eth_call(contract, data, block_tag))
            holders.append({
                "label": label, "address": address.lower(), "balance_raw": str(raw),
                "balance_tokens": raw / scale,
                "share_of_total_supply_pct": (raw / total_raw * 100) if total_raw else None,
                "status": "COMPLETED",
            })
        except Exception as exc:
            holders.append({
                "label": label, "address": address.lower(), "status": "FAILED",
                "error": "BALANCE_UNAVAILABLE",
                "error_type": type(exc).__name__,
            })
    successful = [row for row in holders if row["status"] == "COMPLETED"]
    tracked_raw = sum(int(row["balance_raw"]) for row in successful)
    successful.sort(key=lambda row: row["balance_tokens"], reverse=True)
    return {
        "status": "COMPLETED" if len(successful) == len(holders) else "INCOMPLETE",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "contract_address": contract.lower(),
        "snapshot_block": block, "snapshot_block_number": block,
        "snapshot_block_tag": block_tag,
        "snapshot_block_timestamp": block_timestamp,
        "snapshot_timestamp_status": timestamp_status,
        "snapshot_block_time": (
            datetime.fromtimestamp(block_timestamp, timezone.utc).isoformat()
            if block_timestamp is not None else None
        ),
        "snapshot_age_seconds": (
            max(0, int(datetime.now(timezone.utc).timestamp()) - block_timestamp)
            if block_timestamp is not None else None
        ),
        "token": {"name": name, "symbol": symbol, "decimals": decimals,
                  "total_supply_raw": str(total_raw), "total_supply_tokens": total_raw / scale},
        "tracked_address_count": len(watch_addresses),
        "successful_address_count": len(successful),
        "failed_address_count": len(holders) - len(successful),
        "tracked_balances": successful,
        "failed_balances": [row for row in holders if row["status"] == "FAILED"],
        "tracked_addresses_combined_balance_tokens": tracked_raw / scale,
        "tracked_addresses_combined_share_of_total_supply_pct": (tracked_raw / total_raw * 100 if total_raw else None),
        "warning": "Only supplied/configured addresses are included; this is NOT complete holder distribution or top-holder discovery.",
    }
