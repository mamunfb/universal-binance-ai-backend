from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.providers.evm_rpc import EVMRPCProvider


_TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"


def _validate_index_scope(chain_id: int, contract: str, start: int, end: int) -> str:
    if isinstance(chain_id, bool) or not isinstance(chain_id, int) or chain_id < 0:
        raise ValueError("chain_id must be a non-negative integer")
    if not isinstance(contract, str) or len(contract) != 42 or not contract.startswith("0x"):
        raise ValueError("contract must be a 20-byte 0x-prefixed address")
    try:
        int(contract[2:], 16)
    except ValueError as exc:
        raise ValueError("contract must be a valid hexadecimal address") from exc
    if (isinstance(start, bool) or not isinstance(start, int) or start < 0
            or isinstance(end, bool) or not isinstance(end, int) or end < start):
        raise ValueError("block range must contain non-negative integers with end >= start")
    return contract.lower()


class EVMTransferStore:
    """Persistent, idempotent storage for indexed ERC-20 Transfer logs."""

    def __init__(self, database_path: str) -> None:
        self.database_path = database_path
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(database_path) as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS evm_transfer_logs (
                    chain_id INTEGER NOT NULL,
                    contract_address TEXT NOT NULL,
                    transaction_hash TEXT NOT NULL,
                    log_index INTEGER NOT NULL,
                    block_number INTEGER NOT NULL,
                    from_address TEXT NOT NULL,
                    to_address TEXT NOT NULL,
                    amount_raw TEXT NOT NULL,
                    removed INTEGER NOT NULL DEFAULT 0,
                    indexed_at TEXT NOT NULL,
                    PRIMARY KEY (chain_id, contract_address, transaction_hash, log_index)
                )
            """)
            connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_evm_transfer_contract_block
                ON evm_transfer_logs(chain_id, contract_address, block_number)
            """)
            connection.execute("""
                CREATE TABLE IF NOT EXISTS evm_transfer_index_ranges (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chain_id INTEGER NOT NULL,
                    contract_address TEXT NOT NULL,
                    from_block INTEGER NOT NULL,
                    to_block INTEGER NOT NULL,
                    transfer_count INTEGER NOT NULL,
                    indexed_at TEXT NOT NULL,
                    UNIQUE(chain_id, contract_address, from_block, to_block)
                )
            """)
            connection.execute("""
                CREATE TABLE IF NOT EXISTS evm_block_headers (
                    chain_id INTEGER NOT NULL,
                    block_number INTEGER NOT NULL,
                    block_hash TEXT NOT NULL,
                    parent_hash TEXT NOT NULL,
                    indexed_at TEXT NOT NULL,
                    PRIMARY KEY (chain_id, block_number)
                )
            """)

    def save_chunk(self, chain_id: int, contract: str, start: int, end: int,
                   logs: list[dict[str, Any]],
                   block_headers: list[dict[str, Any]] | None = None) -> int:
        contract = _validate_index_scope(chain_id, contract, start, end)
        if not isinstance(logs, list):
            raise ValueError("logs must be a list")
        now = datetime.now(timezone.utc).isoformat()
        if block_headers is None:
            block_headers = []
        if not isinstance(block_headers, list):
            raise ValueError("block_headers must be a list")
        normalized_headers = []
        seen_header_numbers = set()
        for header in block_headers:
            if not isinstance(header, dict):
                raise ValueError("Block header checkpoints must be objects")
            number = header.get("number")
            block_hash = header.get("hash")
            parent_hash = header.get("parent_hash")
            if (isinstance(number, bool) or not isinstance(number, int) or not start <= number <= end
                    or number in seen_header_numbers):
                raise ValueError("Block header checkpoint number is invalid or duplicated")
            for value in (block_hash, parent_hash):
                if (not isinstance(value, str) or len(value) != 66 or not value.startswith("0x")
                        or any(ch not in "0123456789abcdefABCDEF" for ch in value[2:])):
                    raise ValueError("Block header checkpoint contains an invalid hash")
            seen_header_numbers.add(number)
            normalized_headers.append((chain_id, number, block_hash.lower(), parent_hash.lower(), now))
        normalized_headers.sort(key=lambda item: item[1])
        for previous_header, current_header in zip(normalized_headers, normalized_headers[1:]):
            if (current_header[1] == previous_header[1] + 1
                    and current_header[3] != previous_header[2]):
                raise ValueError("Block header checkpoints have inconsistent parent linkage")
        rows = []
        seen_log_ids: set[tuple[str, int]] = set()
        for log in logs:
            if not isinstance(log, dict):
                raise ValueError("RPC returned a non-object log; refusing to mark this block range complete")
            topics = log.get("topics")
            tx_hash = log.get("transactionHash")
            if (not isinstance(topics, list) or len(topics) != 3
                    or not all(isinstance(topic, str) for topic in topics)
                    or topics[0].lower() != _TRANSFER_TOPIC
                    or not isinstance(tx_hash, str) or len(tx_hash) != 66
                    or not tx_hash.startswith("0x")):
                raise ValueError("RPC returned a malformed ERC-20 Transfer log; refusing to mark this block range complete")
            block_hex, index_hex, data = log.get("blockNumber"), log.get("logIndex"), log.get("data")
            if not all(isinstance(value, str) and value.startswith("0x")
                       for value in (block_hex, index_hex, data)):
                raise ValueError("RPC Transfer log is missing blockNumber, logIndex, or data")
            try:
                if (len(tx_hash) != 66 or len(tx_hash[2:]) != 64
                        or len(block_hex) < 3 or len(index_hex) < 3 or len(data) != 66
                        or len(topics[1]) != 66 or len(topics[2]) != 66
                        or any(character not in "0123456789abcdefABCDEF"
                               for value in (tx_hash[2:], block_hex[2:], index_hex[2:],
                                             data[2:], topics[0][2:], topics[1][2:], topics[2][2:])
                               for character in value)):
                    raise ValueError("Transfer log contains malformed hexadecimal fields")
                block_number, log_index, raw_value = int(block_hex, 16), int(index_hex, 16), int(data, 16)
                if topics[1][2:26] != "0" * 24 or topics[2][2:26] != "0" * 24:
                    raise ValueError("Transfer log contains invalid indexed address padding")
                sender, recipient = "0x" + topics[1][-40:].lower(), "0x" + topics[2][-40:].lower()
                returned_contract = log.get("address")
                if returned_contract is not None:
                    if (not isinstance(returned_contract, str) or len(returned_contract) != 42
                            or not returned_contract.startswith("0x")
                            or returned_contract.lower() != contract):
                        raise ValueError("RPC Transfer log contract does not match requested contract")
                removed = log.get("removed", False)
                if not isinstance(removed, bool):
                    raise ValueError("RPC Transfer log removed flag must be Boolean")
            except (ValueError, TypeError) as exc:
                raise ValueError("RPC returned an invalid Transfer log; refusing to mark this block range complete") from exc
            if not (start <= block_number <= end) or raw_value < 0:
                raise ValueError("RPC Transfer log falls outside the requested range or has a negative amount")
            log_identity = (tx_hash.lower(), log_index)
            if log_identity in seen_log_ids:
                raise ValueError("RPC returned a duplicate transactionHash/logIndex within one block chunk")
            seen_log_ids.add(log_identity)
            rows.append((chain_id, contract, tx_hash.lower(), log_index, block_number,
                         sender, recipient, str(raw_value), int(removed), now))
        with sqlite3.connect(self.database_path) as connection:
            first_divergence = None
            previous_unchanged_checkpoint = None
            for _, number, block_hash, parent_hash, _ in normalized_headers:
                existing = connection.execute(
                    "SELECT block_hash FROM evm_block_headers WHERE chain_id=? AND block_number=?",
                    (chain_id, number),
                ).fetchone()
                previous = connection.execute(
                    "SELECT block_hash FROM evm_block_headers WHERE chain_id=? AND block_number=?",
                    (chain_id, number - 1),
                ).fetchone() if number > 0 else None
                mismatch = bool(existing and existing[0] != block_hash) or bool(
                    previous and previous[0] != parent_hash
                )
                if mismatch:
                    if previous_unchanged_checkpoint is None:
                        prior_anchor = connection.execute(
                            """SELECT block_number FROM evm_block_headers
                               WHERE chain_id=? AND block_number<?
                               ORDER BY block_number DESC LIMIT 1""",
                            (chain_id, number),
                        ).fetchone()
                        previous_unchanged_checkpoint = prior_anchor[0] if prior_anchor else None
                    earliest_possible = (
                        previous_unchanged_checkpoint + 1
                        if previous_unchanged_checkpoint is not None
                        else number
                    )
                    first_divergence = (
                        earliest_possible if first_divergence is None
                        else min(first_divergence, earliest_possible)
                    )
                elif existing and existing[0] == block_hash:
                    previous_unchanged_checkpoint = number
            if first_divergence is not None:
                connection.execute(
                    "DELETE FROM evm_transfer_logs WHERE chain_id=? AND block_number>=?",
                    (chain_id, first_divergence),
                )
                connection.execute(
                    "DELETE FROM evm_transfer_index_ranges WHERE chain_id=? AND to_block>=?",
                    (chain_id, first_divergence),
                )
                connection.execute(
                    "DELETE FROM evm_block_headers WHERE chain_id=? AND block_number>=?",
                    (chain_id, first_divergence),
                )
            connection.executemany("""
                INSERT INTO evm_transfer_logs
                (chain_id, contract_address, transaction_hash, log_index, block_number,
                 from_address, to_address, amount_raw, removed, indexed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(chain_id, contract_address, transaction_hash, log_index)
                DO UPDATE SET block_number=excluded.block_number,
                    from_address=excluded.from_address, to_address=excluded.to_address,
                    amount_raw=excluded.amount_raw, removed=excluded.removed,
                    indexed_at=excluded.indexed_at
            """, rows)
            connection.execute("""
                INSERT INTO evm_transfer_index_ranges
                (chain_id, contract_address, from_block, to_block, transfer_count, indexed_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(chain_id, contract_address, from_block, to_block)
                DO UPDATE SET transfer_count=excluded.transfer_count, indexed_at=excluded.indexed_at
            """, (chain_id, contract, start, end, len(rows), now))
            connection.executemany("""
                INSERT INTO evm_block_headers
                (chain_id, block_number, block_hash, parent_hash, indexed_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(chain_id, block_number)
                DO UPDATE SET block_hash=excluded.block_hash,
                    parent_hash=excluded.parent_hash, indexed_at=excluded.indexed_at
            """, normalized_headers)
        return len(rows)

    def history(self, chain_id: int, contract: str, from_block: int, to_block: int,
                limit: int = 1000) -> list[dict[str, Any]]:
        contract = _validate_index_scope(chain_id, contract, from_block, to_block)
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100_000:
            raise ValueError("limit must be an integer between 1 and 100000")
        with sqlite3.connect(self.database_path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute("""
                SELECT transaction_hash, log_index, block_number, from_address,
                       to_address, amount_raw, removed, indexed_at
                FROM evm_transfer_logs
                WHERE chain_id=? AND contract_address=? AND block_number BETWEEN ? AND ?
                  AND removed=0
                ORDER BY block_number DESC, log_index DESC LIMIT ?
            """, (chain_id, contract.lower(), from_block, to_block, limit)).fetchall()
            return [dict(row) for row in rows]

    def address_flow_summary(self, chain_id: int, contract: str, from_block: int,
                             to_block: int, decimals: int, limit: int = 50) -> dict[str, Any]:
        contract = _validate_index_scope(chain_id, contract, from_block, to_block)
        if isinstance(decimals, bool) or not isinstance(decimals, int) or not 0 <= decimals <= 36:
            raise ValueError("decimals must be an integer between 0 and 36")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 200:
            raise ValueError("limit must be an integer between 1 and 200")
        if not 0 <= decimals <= 36:
            raise ValueError("decimals must be between 0 and 36")
        if not 1 <= limit <= 200:
            raise ValueError("limit must be between 1 and 200")
        with sqlite3.connect(self.database_path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute("""
                SELECT from_address, to_address, amount_raw
                FROM evm_transfer_logs
                WHERE chain_id=? AND contract_address=? AND block_number BETWEEN ? AND ? AND removed=0
            """, (chain_id, contract.lower(), from_block, to_block)).fetchall()
        aggregates: dict[str, dict[str, int]] = {}
        for row in rows:
            raw = int(row["amount_raw"])
            sender = aggregates.setdefault(row["from_address"], {"sent": 0, "received": 0, "count": 0})
            recipient = aggregates.setdefault(row["to_address"], {"sent": 0, "received": 0, "count": 0})
            sender["sent"] += raw
            sender["count"] += 1
            recipient["received"] += raw
            recipient["count"] += 1
        scale = 10 ** decimals
        flows = [{
            "address": address,
            "sent_raw": str(values["sent"]),
            "received_raw": str(values["received"]),
            "net_received_raw": str(values["received"] - values["sent"]),
            "sent_tokens": values["sent"] / scale,
            "received_tokens": values["received"] / scale,
            "net_received_tokens": (values["received"] - values["sent"]) / scale,
            "transfer_count": values["count"],
        } for address, values in aggregates.items()]
        flows.sort(key=lambda item: int(item["net_received_raw"]), reverse=True)
        return {
            "transfer_counted_address_count": len(flows),
            "top_net_receivers": flows[:limit],
            "top_net_senders": sorted(flows, key=lambda item: int(item["net_received_raw"]))[:limit],
            "warning": "Computed only from logs currently stored in SQLite for the requested range. Results are not complete unless indexed coverage spans the full requested range; address flow is not a holder balance or ownership attribution.",
        }

    def range_coverage(self, chain_id: int, contract: str, from_block: int,
                       to_block: int) -> dict[str, Any]:
        contract = _validate_index_scope(chain_id, contract, from_block, to_block)
        ranges = self.coverage(chain_id, contract)
        relevant = sorted(
            (max(from_block, row["from_block"]), min(to_block, row["to_block"]))
            for row in ranges
            if row["to_block"] >= from_block and row["from_block"] <= to_block
        )
        cursor = from_block
        gaps = []
        for start, end in relevant:
            if end < cursor:
                continue
            if start > cursor:
                gaps.append({"from": cursor, "to": start - 1})
            cursor = max(cursor, end + 1)
            if cursor > to_block:
                break
        if cursor <= to_block:
            gaps.append({"from": cursor, "to": to_block})
        return {
            "complete": not gaps,
            "requested_range": {"from": from_block, "to": to_block},
            "covered_through": cursor - 1 if cursor > from_block else None,
            "gaps": gaps,
            "indexed_ranges": relevant,
        }

    def smart_money_activity(self, chain_id: int, contract: str, from_block: int,
                             to_block: int, decimals: int, registry: dict[str, Any],
                             limit: int = 100) -> dict[str, Any]:
        contract = _validate_index_scope(chain_id, contract, from_block, to_block)
        if isinstance(decimals, bool) or not isinstance(decimals, int) or not 0 <= decimals <= 36:
            raise ValueError("decimals must be an integer between 0 and 36")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1000:
            raise ValueError("limit must be an integer between 1 and 1000")
        if not 0 <= decimals <= 36:
            raise ValueError("decimals must be between 0 and 36")
        with sqlite3.connect(self.database_path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute("""
                SELECT from_address, to_address, amount_raw, block_number, transaction_hash
                FROM evm_transfer_logs
                WHERE chain_id=? AND contract_address=? AND block_number BETWEEN ? AND ? AND removed=0
                ORDER BY block_number
            """, (chain_id, contract.lower(), from_block, to_block)).fetchall()
        verified = {
            item["address"]: item for item in registry.get("wallets", [])
            if item.get("label") == "smart_money" and item.get("verification_status") == "verified"
        }
        totals: dict[str, dict[str, Any]] = {}
        for row in rows:
            raw = int(row["amount_raw"])
            for address, sent, received in (
                (row["from_address"], raw, 0), (row["to_address"], 0, raw)
            ):
                if address not in verified:
                    continue
                item = totals.setdefault(address, {
                    "sent_raw": 0, "received_raw": 0, "transfer_count": 0,
                    "first_block": row["block_number"], "last_block": row["block_number"],
                    "transaction_hashes": set(),
                })
                item["sent_raw"] += sent
                item["received_raw"] += received
                item["transfer_count"] += 1
                item["first_block"] = min(item["first_block"], row["block_number"])
                item["last_block"] = max(item["last_block"], row["block_number"])
                item["transaction_hashes"].add(row["transaction_hash"])
        scale = 10 ** decimals
        activity = []
        for address, values in totals.items():
            net = values["received_raw"] - values["sent_raw"]
            activity.append({
                "address": address,
                "entity_name": verified[address].get("entity_name"),
                "evidence_url": verified[address].get("evidence_url"),
                "sent_raw": str(values["sent_raw"]),
                "received_raw": str(values["received_raw"]),
                "net_received_raw": str(net),
                "sent_tokens": values["sent_raw"] / scale,
                "received_tokens": values["received_raw"] / scale,
                "net_received_tokens": net / scale,
                "transfer_count": values["transfer_count"],
                "unique_transactions": len(values["transaction_hashes"]),
                "first_activity_block": values["first_block"],
                "last_activity_block": values["last_block"],
                "flow_direction": "NET_INFLOW" if net > 0 else "NET_OUTFLOW" if net < 0 else "NEUTRAL",
            })
        activity.sort(key=lambda item: abs(int(item["net_received_raw"])), reverse=True)
        inflows = [item for item in activity if int(item["net_received_raw"]) > 0]
        outflows = [item for item in activity if int(item["net_received_raw"]) < 0]
        collective_net_raw = sum(int(item["net_received_raw"]) for item in activity)
        cohort = {
            "net_inflow_wallet_count": len(inflows),
            "net_outflow_wallet_count": len(outflows),
            "neutral_wallet_count": len(activity) - len(inflows) - len(outflows),
            "collective_net_received_raw": str(collective_net_raw),
            "collective_net_received_tokens": collective_net_raw / scale,
            "direction": "NET_INFLOW" if collective_net_raw > 0 else "NET_OUTFLOW" if collective_net_raw < 0 else "NEUTRAL",
            "inflow_wallet_addresses": [item["address"] for item in inflows],
            "outflow_wallet_addresses": [item["address"] for item in outflows],
        }
        return {
            "verified_smart_money_wallets_found": len(activity),
            "wallets": activity[:limit],
            "cohort_summary": cohort,
            "matched_transfer_count": len(rows),
            "warning": "Only operator-verified smart_money registry addresses are included. Cohort direction is a net sum of observed ERC-20 transfers among those addresses, not evidence of coordinated intent, exchange trading, portfolio holdings, realized profit, or a prediction. Coverage must be checked separately.",
        }

    def smart_money_accumulation_trend(self, chain_id: int, contract: str,
                                       from_block: int, to_block: int, decimals: int,
                                       registry: dict[str, Any], window_blocks: int = 1000) -> dict[str, Any]:
        contract = _validate_index_scope(chain_id, contract, from_block, to_block)
        if isinstance(decimals, bool) or not isinstance(decimals, int) or not 0 <= decimals <= 36:
            raise ValueError("decimals must be an integer between 0 and 36")
        if isinstance(window_blocks, bool) or not isinstance(window_blocks, int) or not 1 <= window_blocks <= 1_000_000:
            raise ValueError("window_blocks must be an integer between 1 and 1000000")
        if not 1 <= window_blocks <= 1_000_000:
            raise ValueError("window_blocks must be between 1 and 1000000")
        if not 0 <= decimals <= 36:
            raise ValueError("decimals must be between 0 and 36")
        verified = {
            item["address"] for item in registry.get("wallets", [])
            if item.get("label") == "smart_money" and item.get("verification_status") == "verified"
        }
        with sqlite3.connect(self.database_path) as connection:
            rows = connection.execute("""
                SELECT from_address, to_address, amount_raw, block_number
                FROM evm_transfer_logs
                WHERE chain_id=? AND contract_address=? AND block_number BETWEEN ? AND ? AND removed=0
                ORDER BY block_number
            """, (chain_id, contract.lower(), from_block, to_block)).fetchall()
        bins: dict[int, dict[str, Any]] = {}
        cumulative_raw = 0
        scale = 10 ** decimals
        for sender, recipient, amount_text, block in rows:
            raw = int(amount_text)
            net = (raw if recipient in verified else 0) - (raw if sender in verified else 0)
            if not net:
                continue
            window_start = from_block + ((block - from_block) // window_blocks) * window_blocks
            item = bins.setdefault(window_start, {"from_block": window_start,
                "to_block": min(window_start + window_blocks - 1, to_block),
                "net_flow_raw": 0, "transfer_events": 0})
            item["net_flow_raw"] += net
            item["transfer_events"] += 1
        trend = []
        for start in sorted(bins):
            item = bins[start]
            cumulative_raw += item["net_flow_raw"]
            trend.append({
                "from_block": item["from_block"], "to_block": item["to_block"],
                "net_flow_raw": str(item["net_flow_raw"]),
                "net_flow_tokens": item["net_flow_raw"] / scale,
                "cumulative_net_flow_raw": str(cumulative_raw),
                "cumulative_net_flow_tokens": cumulative_raw / scale,
                "transfer_events": item["transfer_events"],
                "direction": "NET_INFLOW" if item["net_flow_raw"] > 0 else "NET_OUTFLOW" if item["net_flow_raw"] < 0 else "NEUTRAL",
            })
        return {
            "window_blocks": window_blocks,
            "window_count_with_activity": len(trend),
            "windows": trend,
            "warning": "Cumulative net flow starts at zero at the requested from_block. It is not a wallet balance or total holdings; windows without matching transfers are omitted.",
        }


    def verified_label_flows(self, chain_id: int, contract: str, from_block: int,
                             to_block: int, decimals: int, registry: dict[str, Any]) -> dict[str, Any]:
        contract = _validate_index_scope(chain_id, contract, from_block, to_block)
        if isinstance(decimals, bool) or not isinstance(decimals, int) or not 0 <= decimals <= 36:
            raise ValueError("decimals must be an integer between 0 and 36")
        """Aggregate indexed transfer flow for verified registry labels, cancelling cohort-internal transfers."""
        if not 0 <= decimals <= 36:
            raise ValueError("decimals must be between 0 and 36")
        verified = {
            item["address"]: item for item in registry.get("wallets", [])
            if item.get("verification_status") == "verified"
            and item.get("label") in {"exchange", "fund", "market_maker",
                                      "protocol_treasury", "smart_money", "whale"}
        }
        with sqlite3.connect(self.database_path) as connection:
            rows = connection.execute("""
                SELECT from_address, to_address, amount_raw
                FROM evm_transfer_logs
                WHERE chain_id=? AND contract_address=?
                  AND block_number BETWEEN ? AND ? AND removed=0
            """, (chain_id, contract.lower(), from_block, to_block)).fetchall()
        grouped: dict[str, dict[str, Any]] = {}
        for sender, recipient, amount_text in rows:
            raw = int(amount_text)
            sender_entry = verified.get(sender)
            recipient_entry = verified.get(recipient)
            if sender_entry:
                label = sender_entry["label"]
                item = grouped.setdefault(label, {"wallets": set(), "sent_raw": 0,
                                                   "received_raw": 0, "transfer_events": 0})
                item["wallets"].add(sender)
                item["sent_raw"] += raw
                item["transfer_events"] += 1
            if recipient_entry:
                label = recipient_entry["label"]
                item = grouped.setdefault(label, {"wallets": set(), "sent_raw": 0,
                                                   "received_raw": 0, "transfer_events": 0})
                item["wallets"].add(recipient)
                item["received_raw"] += raw
                item["transfer_events"] += 1
        scale = 10 ** decimals
        result = {}
        for label, item in grouped.items():
            net = item["received_raw"] - item["sent_raw"]
            result[label] = {
                "verified_wallet_count": len(item["wallets"]),
                "sent_raw": str(item["sent_raw"]),
                "received_raw": str(item["received_raw"]),
                "net_received_raw": str(net),
                "sent_tokens": item["sent_raw"] / scale,
                "received_tokens": item["received_raw"] / scale,
                "net_received_tokens": net / scale,
                "transfer_events_involving_cohort": item["transfer_events"],
                "direction": "NET_INFLOW" if net > 0 else "NET_OUTFLOW" if net < 0 else "NEUTRAL",
            }
        return {
            "verified_label_flows": result,
            "warning": "Only operator-verified registry entries are included. Transfers between wallets in the same label cohort are included in gross sent/received but cancel in net flow. Transfers are not proof of exchange deposits, sales, purchases, ownership, or investment intent.",
        }

    def coverage(self, chain_id: int, contract: str) -> list[dict[str, Any]]:
        with sqlite3.connect(self.database_path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute("""
                SELECT from_block, to_block, transfer_count, indexed_at
                FROM evm_transfer_index_ranges
                WHERE chain_id=? AND contract_address=?
                ORDER BY from_block
            """, (chain_id, contract.lower())).fetchall()
            return [dict(row) for row in rows]


async def index_erc20_transfer_history(
    provider: EVMRPCProvider,
    store: EVMTransferStore,
    contract: str,
    from_block: int,
    to_block: int,
    chunk_size: int,
    max_total_blocks: int,
) -> dict[str, Any]:
    contract = _validate_index_scope(0, contract, from_block, to_block)
    if isinstance(chunk_size, bool) or not isinstance(chunk_size, int) or not 1 <= chunk_size <= 2000:
        raise ValueError("chunk_size must be an integer between 1 and 2000")
    if (isinstance(max_total_blocks, bool) or not isinstance(max_total_blocks, int)
            or max_total_blocks < 1):
        raise ValueError("max_total_blocks must be a positive integer")
    total_blocks = to_block - from_block + 1
    if total_blocks > max_total_blocks:
        raise ValueError(f"Requested history exceeds maximum of {max_total_blocks} blocks")
    chain_id = await provider.chain_id()
    if isinstance(chain_id, bool) or not isinstance(chain_id, int) or chain_id < 0:
        raise ValueError("Provider returned an invalid chain_id")
    latest_block = await provider.block_number()
    if isinstance(latest_block, bool) or not isinstance(latest_block, int) or latest_block < 0:
        raise ValueError("Provider returned an invalid latest block number")
    if to_block > latest_block:
        raise ValueError(f"to_block {to_block} is ahead of latest block {latest_block}")
    next_block = from_block
    indexed_logs = 0
    completed_chunks = 0
    try:
        while next_block <= to_block:
            chunk_end = min(next_block + chunk_size - 1, to_block)
            headers = []
            header_method = getattr(provider, "block_header", None)
            if not callable(header_method):
                raise ValueError("EVM provider does not support canonical block-header checkpoints")
            first_header = await header_method(next_block)
            headers.append(first_header)
            if chunk_end != next_block:
                headers.append(await header_method(chunk_end))
            logs = await provider.token_transfer_logs(
                contract, next_block, chunk_end, max_block_span=chunk_size
            )
            indexed_logs += store.save_chunk(
                chain_id, contract, next_block, chunk_end, logs, block_headers=headers
            )
            completed_chunks += 1
            next_block = chunk_end + 1
    except Exception as exc:
        return {
            "status": "PARTIAL" if completed_chunks else "FAILED",
            "chain_id": chain_id, "contract_address": contract.lower(),
            "requested_range": {"from": from_block, "to": to_block},
            "completed_range": {"from": from_block, "to": next_block - 1} if completed_chunks else None,
            "next_block_to_retry": next_block, "completed_chunks": completed_chunks,
            "stored_log_count_including_replayed_chunks": indexed_logs,
            "error": "UPSTREAM_UNAVAILABLE",
            "error_type": type(exc).__name__,
            "coverage_note": "Only fully successful chunks are recorded. Retry from next_block_to_retry; writes are idempotent.",
        }
    return {
        "status": "COMPLETED", "chain_id": chain_id, "contract_address": contract.lower(),
        "requested_range": {"from": from_block, "to": to_block},
        "completed_range": {"from": from_block, "to": to_block},
        "next_block_to_retry": None, "completed_chunks": completed_chunks,
        "stored_log_count_including_replayed_chunks": indexed_logs,
        "coverage": store.coverage(chain_id, contract),
        "warning": "Coverage applies only to successful indexed ranges for this contract and chain. It does not prove deployment-to-present completeness unless the requested range starts at deployment and all ranges are indexed.",
    }
