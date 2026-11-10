from typing import Any

import httpx


class BinanceSpotProvider:
    """Small async client for Binance Spot public market-data endpoints."""

    def __init__(self, base_url: str, timeout_seconds: float = 15.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    async def _get(self, path: str) -> Any:
        timeout = httpx.Timeout(self.timeout_seconds)
        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            headers={"User-Agent": "universal-binance-ai-backend/0.1.0"},
        ) as client:
            response = await client.get(path)
            response.raise_for_status()
            return response.json()

    async def exchange_info(self) -> dict[str, Any]:
        data = await self._get("/api/v3/exchangeInfo")
        if not isinstance(data, dict) or "symbols" not in data:
            raise ValueError("Unexpected Binance exchangeInfo response")
        return data

    async def all_24h_tickers(self) -> list[dict[str, Any]]:
        data = await self._get("/api/v3/ticker/24hr")
        if not isinstance(data, list):
            raise ValueError("Unexpected Binance 24hr ticker response")
        return data

    async def klines(
        self, symbol: str, interval: str = "1h", limit: int = 500
    ) -> list[list[Any]]:
        data = await self._get(
            f"/api/v3/klines?symbol={symbol.upper()}&interval={interval}&limit={limit}"
        )
        if not isinstance(data, list):
            raise ValueError("Unexpected Binance klines response")
        return data
