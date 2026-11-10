"""Private MCP stdio adapter for the personal crypto intelligence API.

Run one process per AI client and provide that client's key through environment
variables. The server never accepts API keys as tool arguments.
"""
from __future__ import annotations

import json
import os
from typing import Any
from urllib.parse import quote

import httpx
from mcp.server.fastmcp import FastMCP

CLIENT_NAMES = {"chatgpt", "gemini", "manus", "claude", "perplexity"}


def _load_credentials() -> tuple[str, str, str]:
    base_url = os.environ.get("PERSONAL_API_BASE_URL", "").rstrip("/")
    client_name = os.environ.get("MCP_CLIENT_NAME", "").lower()
    raw_keys = os.environ.get("AI_CLIENT_API_KEYS", "{}")
    try:
        keys = json.loads(raw_keys)
    except json.JSONDecodeError as exc:
        raise RuntimeError("AI_CLIENT_API_KEYS must contain valid JSON") from exc
    if not isinstance(keys, dict):
        raise RuntimeError("AI_CLIENT_API_KEYS must be a JSON object")
    if client_name not in CLIENT_NAMES:
        raise RuntimeError("MCP_CLIENT_NAME must be one of the five configured personal clients")
    api_key = keys.get(client_name)
    if not isinstance(api_key, str) or len(api_key) < 32:
        raise RuntimeError(f"A strong API key for {client_name} is not configured")
    if not base_url.startswith("https://") and not (
        base_url.startswith("http://") and os.environ.get("APP_ENV", "development") == "development"
    ):
        raise RuntimeError("PERSONAL_API_BASE_URL must use HTTPS outside local development")
    return base_url, client_name, api_key


BASE_URL, CLIENT_NAME, API_KEY = _load_credentials()
mcp = FastMCP(f"Personal Crypto Intelligence ({CLIENT_NAME})")


def _get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Call only a fixed, read-only API path with the process-scoped client key."""
    with httpx.Client(timeout=30.0) as client:
        response = client.get(
            f"{BASE_URL}{path}",
            params=params,
            headers={"Authorization": f"Bearer {API_KEY}", "Accept": "application/json"},
        )
        response.raise_for_status()
        return response.json()


@mcp.tool()
def get_spot_klines(symbol: str, interval: str = "1h", limit: int = 100) -> dict:
    """Get read-only Binance Spot OHLCV candles for a symbol and interval."""
    if not 1 <= limit <= 1000:
        raise ValueError("limit must be between 1 and 1000")
    return _get(f"/api/v1/markets/spot/klines/{quote(symbol.upper(), safe='')}", {"interval": interval, "limit": limit})


@mcp.tool()
def get_spot_technical_analysis(symbol: str, interval: str = "1h", limit: int = 500) -> dict:
    """Get the backend's read-only Spot technical indicator analysis."""
    if not 1 <= limit <= 1000:
        raise ValueError("limit must be between 1 and 1000")
    return _get(f"/api/v1/analysis/spot/technical/{quote(symbol.upper(), safe='')}", {"interval": interval, "limit": limit})


@mcp.tool()
def get_futures_derivatives(symbol: str) -> dict:
    """Get read-only USD-M futures derivatives context for a symbol."""
    return _get(f"/api/v1/analysis/futures/usdm/derivatives/{quote(symbol.upper(), safe='')}")


@mcp.tool()
def get_news_intelligence(symbols: str = "BTC,ETH", hours: int = 72, limit: int = 100) -> dict:
    """Get source-aware crypto news intelligence; this is not a price forecast."""
    if not 1 <= hours <= 720 or not 1 <= limit <= 500:
        raise ValueError("hours must be 1..720 and limit must be 1..500")
    return _get("/api/v1/news/intelligence", {"symbols": symbols, "hours": hours, "limit": limit})


@mcp.tool()
def get_cross_chain_token_intelligence(
    asset_id: str,
    from_block: int,
    to_block: int,
    decimals: int = 18,
    limit: int = 50,
    window_blocks: int = 1000,
) -> dict:
    """Get indexed cross-chain token flows and verified cohort intelligence.

    Coverage, freshness, and incomplete_reasons must be preserved when interpreting
    the result. Net transfer flow does not prove buying, selling, or intent.
    """
    if from_block < 0 or to_block < from_block:
        raise ValueError("Require 0 <= from_block <= to_block")
    if not 0 <= decimals <= 36 or not 1 <= limit <= 100 or not 1 <= window_blocks <= 100000:
        raise ValueError("decimals, limit, or window_blocks is outside supported bounds")
    return _get(
        f"/api/v1/onchain/evm/cross-chain/token/{quote(asset_id, safe='')}/intelligence",
        {
            "from_block": from_block,
            "to_block": to_block,
            "decimals": decimals,
            "limit": limit,
            "window_blocks": window_blocks,
        },
    )


@mcp.tool()
def get_liquidation_collector_status() -> dict:
    """Check whether the optional liquidation snapshot collector is enabled."""
    return _get("/api/v1/analysis/futures/liquidations/status")


if __name__ == "__main__":
    # stdio transport keeps the adapter local to its configured AI client process.
    mcp.run(transport="stdio")
