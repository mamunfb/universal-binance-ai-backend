from typing import Any

import httpx


class BinanceFuturesProvider:
    """Async public-data client for Binance USDⓈ-M and COIN-M futures."""

    BASE_URLS = {
        "USD_M": "https://fapi.binance.com",
        "COIN_M": "https://dapi.binance.com",
    }

    def __init__(self, market: str, timeout_seconds: float = 15.0) -> None:
        normalized = market.upper().replace("-", "_")
        if normalized not in self.BASE_URLS:
            raise ValueError("market must be USD_M or COIN_M")
        self.market = normalized
        self.base_url = self.BASE_URLS[normalized]
        self.timeout_seconds = timeout_seconds
        self.prefix = "/fapi/v1" if normalized == "USD_M" else "/dapi/v1"

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        timeout = httpx.Timeout(self.timeout_seconds)
        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            headers={"User-Agent": "universal-binance-ai-backend/0.1.0"},
        ) as client:
            response = await client.get(path, params=params)
            response.raise_for_status()
            return response.json()

    async def exchange_info(self) -> dict[str, Any]:
        data = await self._get(f"{self.prefix}/exchangeInfo")
        if not isinstance(data, dict) or not isinstance(data.get("symbols"), list):
            raise ValueError(f"Unexpected Binance {self.market} exchangeInfo response")
        return data

    async def all_24h_tickers(self) -> list[dict[str, Any]]:
        data = await self._get(f"{self.prefix}/ticker/24hr")
        if not isinstance(data, list):
            raise ValueError(f"Unexpected Binance {self.market} 24hr ticker response")
        return data

    async def klines(
        self, symbol: str, interval: str = "1h", limit: int = 500
    ) -> list[list[Any]]:
        data = await self._get(
            f"{self.prefix}/klines",
            {"symbol": symbol.upper(), "interval": interval, "limit": limit},
        )
        if not isinstance(data, list):
            raise ValueError(f"Unexpected Binance {self.market} kline response")
        return data
