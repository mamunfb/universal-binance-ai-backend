from typing import Any

import httpx


class BinanceSpotProvider:
    """Small async client for Binance Spot public market-data endpoints."""

    def __init__(self, base_url: str, timeout_seconds: float = 15.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    async def _get(
        self, path: str, params: dict[str, Any] | None = None
    ) -> Any:
        timeout = httpx.Timeout(self.timeout_seconds)
        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            headers={"User-Agent": "universal-binance-ai-backend/0.1.0"},
        ) as client:
            response = await client.get(path, params=params)
            response.raise_for_status()
            return response.json()

    async def price_ticker(self, symbol: str) -> dict[str, Any]:
        if not symbol or not symbol.strip():
            raise ValueError("symbol must not be empty")
        data = await self._get("/api/v3/ticker/price", {"symbol": symbol.upper()})
        if not isinstance(data, dict):
            raise ValueError("Unexpected Binance Spot price ticker response")
        return data

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


    async def all_book_tickers(self) -> list[dict[str, Any]]:
        """Fetch best bid/ask for all Spot symbols in one public request."""
        data = await self._get("/api/v3/ticker/bookTicker")
        if not isinstance(data, list) or any(not isinstance(item, dict) for item in data):
            raise ValueError("Unexpected Binance Spot book-ticker response")
        return data

    async def order_book(self, symbol: str, limit: int = 100) -> dict[str, Any]:
        if not symbol or not symbol.strip():
            raise ValueError("symbol must not be empty")
        if limit not in {1, 5, 10, 20, 50, 100, 500, 1000, 5000}:
            raise ValueError("Unsupported Spot order book limit")
        data = await self._get("/api/v3/depth", {"symbol": symbol.upper(), "limit": limit})
        if not isinstance(data, dict) or not isinstance(data.get("bids"), list) or not isinstance(data.get("asks"), list):
            raise ValueError("Unexpected Binance Spot order book response")
        return data

    async def klines(
        self, symbol: str, interval: str = "1h", limit: int = 500,
        start_time_ms: int | None = None, end_time_ms: int | None = None,
    ) -> list[list[Any]]:
        if not symbol or not symbol.strip():
            raise ValueError("symbol must not be empty")
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        params: dict[str, Any] = {
            "symbol": symbol.upper(), "interval": interval, "limit": limit,
        }
        if start_time_ms is not None:
            params["startTime"] = start_time_ms
        if end_time_ms is not None:
            params["endTime"] = end_time_ms
        data = await self._get("/api/v3/klines", params)
        if not isinstance(data, list):
            raise ValueError("Unexpected Binance klines response")
        return data
