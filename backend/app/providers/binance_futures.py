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

    async def premium_index(self, symbol: str | None = None) -> dict[str, Any] | list[dict[str, Any]]:
        """Fetch mark/index price, current funding rate and next funding time."""
        if symbol is not None and not symbol.strip():
            raise ValueError("symbol must not be empty")
        params = {"symbol": symbol.upper()} if symbol else None
        data = await self._get(f"{self.prefix}/premiumIndex", params)
        if isinstance(data, dict):
            if not data.get("symbol") or "markPrice" not in data or "indexPrice" not in data:
                raise ValueError(f"Unexpected Binance {self.market} premium-index response")
            return data
        if isinstance(data, list) and all(
            isinstance(item, dict) and item.get("symbol")
            and "markPrice" in item and "indexPrice" in item for item in data
        ):
            return data
        raise ValueError(f"Unexpected Binance {self.market} premium-index response")

    async def funding_info(self) -> list[dict[str, Any]]:
        """Fetch per-symbol funding interval adjustments, when present."""
        data = await self._get(f"{self.prefix}/fundingInfo")
        if not isinstance(data, list) or any(not isinstance(item, dict) for item in data):
            raise ValueError(f"Unexpected Binance {self.market} funding-info response")
        return data

    async def funding_rate(
        self, symbol: str, limit: int = 1000,
        start_time_ms: int | None = None, end_time_ms: int | None = None,
    ) -> list[dict[str, Any]]:
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
        data = await self._get(f"{self.prefix}/fundingRate", params)
        if not isinstance(data, list):
            raise ValueError("Unexpected funding rate response")
        return data

    async def open_interest(self, symbol: str) -> dict[str, Any]:
        if not symbol or not symbol.strip():
            raise ValueError("symbol must not be empty")
        data = await self._get(f"{self.prefix}/openInterest", {"symbol": symbol.upper()})
        if not isinstance(data, dict):
            raise ValueError("Unexpected open interest response")
        return data

    async def open_interest_history(
        self, symbol: str, period: str = "1h", limit: int = 30,
        start_time_ms: int | None = None, end_time_ms: int | None = None,
        pair: str | None = None, contract_type: str | None = None,
    ) -> list[dict[str, Any]]:
        if not symbol or not symbol.strip():
            raise ValueError("symbol must not be empty")
        if period not in {"5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d"}:
            raise ValueError("Unsupported open-interest period")
        if not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500")
        if start_time_ms is not None and start_time_ms < 0:
            raise ValueError("start_time_ms must be non-negative")
        if end_time_ms is not None and end_time_ms < 0:
            raise ValueError("end_time_ms must be non-negative")
        if start_time_ms is not None and end_time_ms is not None and end_time_ms < start_time_ms:
            raise ValueError("end_time_ms must be >= start_time_ms")
        if self.market == "COIN_M":
            normalized_pair = (pair or symbol.upper().rsplit("_", 1)[0]).strip().upper()
            if not normalized_pair:
                raise ValueError("pair must not be empty for COIN-M open-interest history")
            params: dict[str, Any] = {
                "pair": normalized_pair, "period": period, "limit": limit,
            }
            if contract_type is not None:
                if contract_type not in {"PERPETUAL", "CURRENT_QUARTER", "NEXT_QUARTER"}:
                    raise ValueError("Unsupported COIN-M contract_type")
                params["contractType"] = contract_type
        else:
            params = {"symbol": symbol.upper(), "period": period, "limit": limit}
        if start_time_ms is not None:
            params["startTime"] = start_time_ms
        if end_time_ms is not None:
            params["endTime"] = end_time_ms
        data = await self._get("/futures/data/openInterestHist", params)
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


    async def all_book_tickers(self) -> list[dict[str, Any]]:
        """Fetch best bid/ask for all Futures symbols in one public request."""
        data = await self._get(f"{self.prefix}/ticker/bookTicker")
        if not isinstance(data, list) or any(not isinstance(item, dict) for item in data):
            raise ValueError(f"Unexpected Binance {self.market} book-ticker response")
        return data

    async def order_book(self, symbol: str, limit: int = 100) -> dict[str, Any]:
        if not symbol or not symbol.strip():
            raise ValueError("symbol must not be empty")
        if limit not in {5, 10, 20, 50, 100, 500, 1000}:
            raise ValueError("Unsupported futures order book limit")
        data = await self._get(f"{self.prefix}/depth", {"symbol": symbol.upper(), "limit": limit})
        if not isinstance(data, dict) or "bids" not in data or "asks" not in data:
            raise ValueError("Unexpected order book response")
        return data

    async def continuous_klines(
        self, pair: str, contract_type: str, interval: str = "1s", limit: int = 500,
    ) -> list[list[Any]]:
        """Fetch USDⓈ-M continuous-contract candles (not symbol-specific klines)."""
        if self.market != "USD_M":
            raise ValueError("continuous klines are supported only for USD_M")
        if not pair or not pair.strip():
            raise ValueError("pair must not be empty")
        if not isinstance(contract_type, str):
            raise ValueError("contract_type must be a supported string")
        allowed_contract_types = {"PERPETUAL", "CURRENT_QUARTER", "NEXT_QUARTER", "TRADIFI_PERPETUAL"}
        normalized_type = contract_type.strip().upper()
        if normalized_type not in allowed_contract_types:
            raise ValueError("unsupported USD_M continuous contract type")
        if interval != "1s":
            raise ValueError("continuous klines currently support only the 1s chart interval")
        if not 1 <= limit <= 1500:
            raise ValueError("limit must be between 1 and 1500")
        params: dict[str, Any] = {
            "pair": pair.strip().upper(), "contractType": normalized_type,
            "interval": interval, "limit": limit,
        }
        data = await self._get("/fapi/v1/continuousKlines", params)
        if not isinstance(data, list):
            raise ValueError("Unexpected Binance USD_M continuous kline response")
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
