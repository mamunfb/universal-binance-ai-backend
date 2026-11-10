from __future__ import annotations

from typing import Any
import httpx

TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"


class EVMRPCProvider:
    """Minimal read-only JSON-RPC provider for EVM-compatible networks."""

    def __init__(self, rpc_url: str, timeout_seconds: float = 20.0) -> None:
        if not rpc_url.startswith("https://"):
            raise ValueError("EVM RPC endpoint must use HTTPS")
        self.rpc_url = rpc_url
        self.timeout_seconds = timeout_seconds
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
        if data.get("error"):
            raise RuntimeError(f"JSON-RPC {method} failed: {data['error']}")
        if "result" not in data:
            raise ValueError(f"JSON-RPC {method} response has no result")
        return data["result"]

    async def chain_id(self) -> int:
        return int(await self._rpc("eth_chainId", []), 16)

    async def block_number(self) -> int:
        return int(await self._rpc("eth_blockNumber", []), 16)

    async def native_balance(self, address: str, block: str = "latest") -> int:
        _validate_address(address)
        return int(await self._rpc("eth_getBalance", [address, block]), 16)

    async def eth_call(self, contract: str, data: str) -> str:
        _validate_address(contract)
        if not isinstance(data, str) or not data.startswith("0x"):
            raise ValueError("eth_call data must be 0x-prefixed hex")
        result = await self._rpc("eth_call", [{"to": contract, "data": data}, "latest"])
        if not isinstance(result, str) or not result.startswith("0x"):
            raise ValueError("Unexpected eth_call result")
        return result

    async def token_transfer_logs(self, contract: str, from_block: int, to_block: int,
                                  max_block_span: int = 2000) -> list[dict[str, Any]]:
        _validate_address(contract)
        if from_block < 0 or to_block < from_block:
            raise ValueError("Invalid block range")
        if to_block - from_block + 1 > max_block_span:
            raise ValueError(f"Block range exceeds configured maximum of {max_block_span}")
        logs = await self._rpc("eth_getLogs", [{
            "address": contract, "fromBlock": hex(from_block), "toBlock": hex(to_block),
            "topics": [TRANSFER_TOPIC],
        }])
        if not isinstance(logs, list):
            raise ValueError("Unexpected eth_getLogs result")
        return logs


def _validate_address(address: str) -> None:
    if not isinstance(address, str) or len(address) != 42 or not address.startswith("0x"):
        raise ValueError("Expected a 20-byte 0x-prefixed EVM address")
    try:
        int(address[2:], 16)
    except ValueError as exc:
        raise ValueError("Invalid hexadecimal EVM address") from exc
