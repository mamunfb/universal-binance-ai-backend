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

    async def price_ticker(self, symbol: str) -> dict[str, Any]:
        if not symbol or not symbol.strip():
            raise ValueError("symbol must not be empty")
        data = await self._get(f"{self.prefix}/ticker/price", {"symbol": symbol.upper()})
        if not isinstance(data, dict):
            raise ValueError(f"Unexpected Binance {self.market} price ticker response")
        return data

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

    async def funding_rate(
        self, symbol: str, limit: int = 1000,
        start_time_ms: int | None = None, end_time_ms: int | None = None,
    ) -> list[dict[str, Any]]:
        if self.market != "USD_M":
            raise NotImplementedError("Funding history adapter is currently enabled for USD_M only")
        if not symbol or not symbol.strip():
            raise ValueError("symbol must not be empty")
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        if start_time_ms is not None and start_time_ms < 0:
            raise ValueError("start_time_ms must be non-negative")
        if end_time_ms is not None and end_time_ms < 0:
            raise ValueError("end_time_ms must be non-negative")
        if start_time_ms is not None and end_time_ms is not None and end_time_ms < start_time_ms:
            raise ValueError("end_time_ms must be >= start_time_ms")
        params: dict[str, Any] = {"symbol": symbol.upper(), "limit": limit}
        if start_time_ms is not None:
            params["startTime"] = start_time_ms
        if end_time_ms is not None:
            params["endTime"] = end_time_ms
        data = await self._get("/fapi/v1/fundingRate", params)
        if not isinstance(data, list):
            raise ValueError("Unexpected funding rate response")
        return data

    async def open_interest(self, symbol: str) -> dict[str, Any]:
        if self.market != "USD_M":
            raise NotImplementedError("Open interest adapter is currently enabled for USD_M only")
        data = await self._get("/fapi/v1/openInterest", {"symbol": symbol.upper()})
        if not isinstance(data, dict):
            raise ValueError("Unexpected open interest response")
        return data

    async def open_interest_history(
        self, symbol: str, period: str = "1h", limit: int = 30
    ) -> list[dict[str, Any]]:
        if self.market != "USD_M":
            raise NotImplementedError("Open interest history is currently enabled for USD_M only")
        data = await self._get(
            "/futures/data/openInterestHist",
            {"symbol": symbol.upper(), "period": period, "limit": limit},
        )
        if not isinstance(data, list):
            raise ValueError("Unexpected open interest history response")
        return data

    async def global_long_short_ratio(
        self, symbol: str, period: str = "1h", limit: int = 30
    ) -> list[dict[str, Any]]:
        if self.market != "USD_M":
            raise NotImplementedError("Global long/short ratio is currently enabled for USD_M only")
        data = await self._get(
            "/futures/data/globalLongShortAccountRatio",
            {"symbol": symbol.upper(), "period": period, "limit": limit},
        )
        if not isinstance(data, list):
            raise ValueError("Unexpected global long/short ratio response")
        return data

    async def taker_long_short_ratio(
        self, symbol: str, period: str = "1h", limit: int = 30
    ) -> list[dict[str, Any]]:
        if self.market != "USD_M":
            raise NotImplementedError("Taker ratio is currently enabled for USD_M only")
        data = await self._get(
            "/futures/data/takerlongshortRatio",
            {"symbol": symbol.upper(), "period": period, "limit": limit},
        )
        if not isinstance(data, list):
            raise ValueError("Unexpected taker ratio response")
        return data

    async def order_book(self, symbol: str, limit: int = 100) -> dict[str, Any]:
        if self.market != "USD_M":
            raise NotImplementedError("Order book adapter is currently enabled for USD_M only")
        data = await self._get("/fapi/v1/depth", {"symbol": symbol.upper(), "limit": limit})
        if not isinstance(data, dict) or "bids" not in data or "asks" not in data:
            raise ValueError("Unexpected order book response")
        return data

    async def klines(
        self, symbol: str, interval: str = "1h", limit: int = 500,
        start_time_ms: int | None = None, end_time_ms: int | None = None,
    ) -> list[list[Any]]:
        if not symbol or not symbol.strip():
            raise ValueError("symbol must not be empty")
        if not 1 <= limit <= 1500:
            raise ValueError("limit must be between 1 and 1500")
        params: dict[str, Any] = {
            "symbol": symbol.upper(), "interval": interval, "limit": limit,
        }
        if start_time_ms is not None:
            params["startTime"] = start_time_ms
        if end_time_ms is not None:
            params["endTime"] = end_time_ms
        data = await self._get(f"{self.prefix}/klines", params)
        if not isinstance(data, list):
            raise ValueError(f"Unexpected Binance {self.market} kline response")
        return data
