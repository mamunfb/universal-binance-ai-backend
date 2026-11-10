from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.providers.evm_rpc import EVMRPCProvider


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

    def save_chunk(self, chain_id: int, contract: str, start: int, end: int,
                   logs: list[dict[str, Any]]) -> int:
        now = datetime.now(timezone.utc).isoformat()
        rows = []
        for log in logs:
            if not isinstance(log, dict):
                raise ValueError("RPC returned a non-object log; refusing to mark this block range complete")
            topics = log.get("topics") or []
            tx_hash = log.get("transactionHash")
            if len(topics) < 3 or not isinstance(tx_hash, str) or len(tx_hash) != 66 or not tx_hash.startswith("0x"):
                raise ValueError("RPC returned a malformed Transfer log; refusing to mark this block range complete")
            block_hex, index_hex, data = log.get("blockNumber"), log.get("logIndex"), log.get("data")
            if not all(isinstance(value, str) and value.startswith("0x")
                       for value in (block_hex, index_hex, data)):
                raise ValueError("RPC Transfer log is missing blockNumber, logIndex, or data")
            try:
                block_number, log_index, raw_value = int(block_hex, 16), int(index_hex, 16), int(data, 16)
                if len(topics[1]) != 66 or len(topics[2]) != 66:
                    raise ValueError("Transfer log contains malformed indexed address topics")
                sender, recipient = "0x" + topics[1][-40:].lower(), "0x" + topics[2][-40:].lower()
                int(sender[2:], 16)
                int(recipient[2:], 16)
            except (ValueError, TypeError) as exc:
                raise ValueError("RPC returned an invalid Transfer log; refusing to mark this block range complete") from exc
            if not (start <= block_number <= end) or raw_value < 0:
                raise ValueError("RPC Transfer log falls outside the requested range or has a negative amount")
            rows.append((chain_id, contract.lower(), tx_hash.lower(), log_index, block_number,
                         sender, recipient, str(raw_value), int(bool(log.get("removed"))), now))
        with sqlite3.connect(self.database_path) as connection:
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
            """, (chain_id, contract.lower(), start, end, len(rows), now))
        return len(rows)

    def history(self, chain_id: int, contract: str, from_block: int, to_block: int,
                limit: int = 1000) -> list[dict[str, Any]]:
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
            "sent_tokens": values["sent"] / scale,
            "received_tokens": values["received"] / scale,
            "net_received_tokens": (values["received"] - values["sent"]) / scale,
            "transfer_count": values["count"],
        } for address, values in aggregates.items()]
        flows.sort(key=lambda item: item["net_received_tokens"], reverse=True)
        return {
            "transfer_counted_address_count": len(flows),
            "top_net_receivers": flows[:limit],
            "top_net_senders": sorted(flows, key=lambda item: item["net_received_tokens"])[:limit],
            "warning": "Computed only from logs currently stored in SQLite for the requested range. Results are not complete unless indexed coverage spans the full requested range; address flow is not a holder balance or ownership attribution.",
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
    if from_block < 0 or to_block < from_block:
        raise ValueError("Invalid block range")
    if chunk_size < 1 or chunk_size > 2000:
        raise ValueError("chunk_size must be between 1 and 2000")
    total_blocks = to_block - from_block + 1
    if total_blocks > max_total_blocks:
        raise ValueError(f"Requested history exceeds maximum of {max_total_blocks} blocks")
    chain_id = await provider.chain_id()
    latest_block = await provider.block_number()
    if to_block > latest_block:
        raise ValueError(f"to_block {to_block} is ahead of latest block {latest_block}")
    next_block = from_block
    indexed_logs = 0
    completed_chunks = 0
    try:
        while next_block <= to_block:
            chunk_end = min(next_block + chunk_size - 1, to_block)
            logs = await provider.token_transfer_logs(
                contract, next_block, chunk_end, max_block_span=chunk_size
            )
            indexed_logs += store.save_chunk(chain_id, contract, next_block, chunk_end, logs)
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
            "error": f"{type(exc).__name__}: {str(exc)[:300]}",
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
