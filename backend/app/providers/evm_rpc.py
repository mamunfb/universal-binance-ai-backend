from __future__ import annotations

from typing import Any
import math
import httpx

TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"


class EVMRPCProvider:
    """Minimal read-only JSON-RPC provider for EVM-compatible networks."""

    def __init__(self, rpc_url: str, timeout_seconds: float = 20.0) -> None:
        if not isinstance(rpc_url, str) or not rpc_url.startswith("https://"):
            raise ValueError("EVM RPC endpoint must use HTTPS")
        if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)) or not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be a positive number")
        self.rpc_url = rpc_url
        self.timeout_seconds = float(timeout_seconds)
        self._request_id = 0

    async def _rpc(self, method: str, params: list[Any], client: httpx.AsyncClient | None = None) -> Any:
        self._request_id += 1
        payload = {"jsonrpc": "2.0", "id": self._request_id, "method": method, "params": params}
        owns_client = client is None
        if client is None:
            client = httpx.AsyncClient(timeout=httpx.Timeout(self.timeout_seconds))
        try:
            response = await client.post(self.rpc_url, json=payload)
            response.raise_for_status()
            data = response.json()
        finally:
            if owns_client:
                await client.aclose()
        if not isinstance(data, dict):
            raise ValueError("Unexpected JSON-RPC response")
        if data.get("jsonrpc") != "2.0":
            raise ValueError("JSON-RPC response has an invalid protocol version")
        if data.get("id") != payload["id"]:
            raise ValueError("JSON-RPC response id does not match request")
        if data.get("error") is not None:
            raise RuntimeError(f"JSON-RPC {method} failed: {data['error']}")
        if "result" not in data:
            raise ValueError(f"JSON-RPC {method} response has no result")
        return data["result"]

    async def chain_id(self) -> int:
        return int(await self._rpc("eth_chainId", []), 16)

    async def block_number(self) -> int:
        return int(await self._rpc("eth_blockNumber", []), 16)

    async def block_timestamp(self, block_number: int) -> int:
        if isinstance(block_number, bool) or not isinstance(block_number, int) or block_number < 0:
            raise ValueError("block_number must be a non-negative integer")
        block = await self._rpc("eth_getBlockByNumber", [hex(block_number), False])
        if not isinstance(block, dict):
            raise ValueError("Unexpected eth_getBlockByNumber result")
        timestamp = block.get("timestamp")
        if not isinstance(timestamp, str) or not timestamp.startswith("0x"):
            raise ValueError("Block response has no valid timestamp")
        try:
            value = int(timestamp, 16)
        except ValueError as exc:
            raise ValueError("Block timestamp is not valid hexadecimal") from exc
        if value < 0:
            raise ValueError("Block timestamp must be non-negative")
        return value

    async def native_balance(self, address: str, block: str = "latest") -> int:
        _validate_address(address)
        return int(await self._rpc("eth_getBalance", [address, block]), 16)

    async def eth_call(self, contract: str, data: str, block: str = "latest") -> str:
        _validate_address(contract)
        if not isinstance(data, str) or not data.startswith("0x"):
            raise ValueError("eth_call data must be 0x-prefixed hex")
        result = await self._rpc("eth_call", [{"to": contract, "data": data}, block])
        if not isinstance(result, str) or not result.startswith("0x"):
            raise ValueError("Unexpected eth_call result")
        return result

    async def token_transfer_logs(self, contract: str, from_block: int, to_block: int,
                                  max_block_span: int = 2000) -> list[dict[str, Any]]:
        _validate_address(contract)
        if (isinstance(from_block, bool) or not isinstance(from_block, int) or
                isinstance(to_block, bool) or not isinstance(to_block, int) or
                from_block < 0 or to_block < from_block):
            raise ValueError("Invalid block range")
        if (isinstance(max_block_span, bool) or not isinstance(max_block_span, int)
                or max_block_span < 1):
            raise ValueError("max_block_span must be a positive integer")
        if to_block - from_block + 1 > max_block_span:
            raise ValueError(f"Block range exceeds configured maximum of {max_block_span}")
        logs = await self._rpc("eth_getLogs", [{
            "address": contract, "fromBlock": hex(from_block), "toBlock": hex(to_block),
            "topics": [TRANSFER_TOPIC],
        }])
        if not isinstance(logs, list) or any(not isinstance(item, dict) for item in logs):
            raise ValueError("Unexpected eth_getLogs result")
        return logs


def _validate_address(address: str) -> None:
    if not isinstance(address, str) or len(address) != 42 or not address.startswith("0x"):
        raise ValueError("Expected a 20-byte 0x-prefixed EVM address")
    try:
        int(address[2:], 16)
    except ValueError as exc:
        raise ValueError("Invalid hexadecimal EVM address") from exc
