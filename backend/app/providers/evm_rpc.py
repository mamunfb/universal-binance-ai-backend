from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit
import asyncio
import json
import math
import httpx

TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"


class EVMRPCProvider:
    """Minimal read-only JSON-RPC provider for EVM-compatible networks."""

    def __init__(
        self, rpc_url: str, timeout_seconds: float = 20.0,
        retry_attempts: int = 2, max_response_bytes: int = 2_097_152,
    ) -> None:
        if not isinstance(rpc_url, str):
            raise ValueError("EVM RPC endpoint must be a valid HTTPS URL")
        try:
            parsed_url = urlsplit(rpc_url)
            valid_url = (
                parsed_url.scheme == "https" and bool(parsed_url.hostname)
                and parsed_url.username is None and parsed_url.password is None
                and parsed_url.fragment == "" and parsed_url.port != 0
                and not any(character.isspace() for character in rpc_url)
            )
        except ValueError:
            valid_url = False
        if not valid_url:
            raise ValueError("EVM RPC endpoint must be a valid HTTPS URL without credentials or fragment")
        if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)) or not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be a positive number")
        if isinstance(retry_attempts, bool) or not isinstance(retry_attempts, int) or not 0 <= retry_attempts <= 3:
            raise ValueError("retry_attempts must be an integer between 0 and 3")
        if isinstance(max_response_bytes, bool) or not isinstance(max_response_bytes, int) or max_response_bytes < 1:
            raise ValueError("max_response_bytes must be a positive integer")
        self.rpc_url = rpc_url
        self.timeout_seconds = float(timeout_seconds)
        self.retry_attempts = retry_attempts
        self.max_response_bytes = max_response_bytes
        self._request_id = 0

    async def _rpc(self, method: str, params: list[Any], client: httpx.AsyncClient | None = None) -> Any:
        self._request_id += 1
        payload = {"jsonrpc": "2.0", "id": self._request_id, "method": method, "params": params}
        owns_client = client is None
        if client is None:
            client = httpx.AsyncClient(timeout=httpx.Timeout(self.timeout_seconds))
        try:
            for attempt in range(self.retry_attempts + 1):
                try:
                    chunks: list[bytes] = []
                    total_bytes = 0
                    async with client.stream(
                        "POST", self.rpc_url, json=payload, follow_redirects=False
                    ) as response:
                        response.raise_for_status()
                        async for chunk in response.aiter_bytes():
                            total_bytes += len(chunk)
                            if total_bytes > self.max_response_bytes:
                                raise ValueError("JSON-RPC response exceeds configured byte limit")
                            chunks.append(chunk)
                    data = json.loads(b"".join(chunks))
                    break
                except httpx.HTTPStatusError as exc:
                    status = exc.response.status_code
                    if status not in (429, 500, 502, 503, 504) or attempt >= self.retry_attempts:
                        raise
                except httpx.TransportError:
                    if attempt >= self.retry_attempts:
                        raise
                await asyncio.sleep(min(0.1 * (2 ** attempt), 0.5))
        finally:
            if owns_client:
                await client.aclose()
        if not isinstance(data, dict):
            raise ValueError("Unexpected JSON-RPC response")
        if data.get("jsonrpc") != "2.0":
            raise ValueError("JSON-RPC response has an invalid protocol version")
        response_id = data.get("id")
        if type(response_id) is not int or response_id != payload["id"]:
            raise ValueError("JSON-RPC response id does not match request")
        has_result = "result" in data
        has_error = "error" in data
        if has_result == has_error:
            raise ValueError(f"JSON-RPC {method} response must contain exactly one of result or error")
        if has_error:
            error = data["error"]
            if (
                not isinstance(error, dict)
                or isinstance(error.get("code"), bool)
                or not isinstance(error.get("code"), int)
                or not isinstance(error.get("message"), str)
                or not error["message"].strip()
            ):
                raise ValueError("JSON-RPC error object has an invalid shape")
            raise RuntimeError(f"JSON-RPC {method} failed with error code {error['code']}")
        return data["result"]

    async def chain_id(self) -> int:
        return int(await self._rpc("eth_chainId", []), 16)

    async def block_number(self) -> int:
        return int(await self._rpc("eth_blockNumber", []), 16)

    async def block_header(self, block_number: int) -> dict[str, Any]:
        """Fetch canonical block identity for reorg checkpoints."""
        if isinstance(block_number, bool) or not isinstance(block_number, int) or block_number < 0:
            raise ValueError("block_number must be a non-negative integer")
        block = await self._rpc("eth_getBlockByNumber", [hex(block_number), False])
        if not isinstance(block, dict):
            raise ValueError("Unexpected eth_getBlockByNumber result")
        number = block.get("number")
        block_hash = block.get("hash")
        parent_hash = block.get("parentHash")
        for field, value in (("number", number), ("hash", block_hash), ("parentHash", parent_hash)):
            if not isinstance(value, str) or not value.startswith("0x"):
                raise ValueError(f"Block response has no valid {field}")
        try:
            parsed_number = int(number, 16)
        except ValueError as exc:
            raise ValueError("Block number is not valid hexadecimal") from exc
        if parsed_number != block_number:
            raise ValueError("Block response number does not match requested block")
        if any(len(value) != 66 or any(ch not in "0123456789abcdefABCDEF" for ch in value[2:])
               for value in (block_hash, parent_hash)):
            raise ValueError("Block response contains an invalid hash")
        return {"number": parsed_number, "hash": block_hash.lower(), "parent_hash": parent_hash.lower()}

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
