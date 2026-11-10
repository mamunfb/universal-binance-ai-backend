from typing import Literal

from fastapi import FastAPI, HTTPException, Query

from app.config import settings
from app.providers.binance_spot import BinanceSpotProvider
from app.services.market_scanner import scan_spot_markets

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description=(
        "Research-only crypto market data API. Initial release covers Binance Spot "
        "public market data; other markets and intelligence providers are planned."
    ),
)


def get_spot_provider() -> BinanceSpotProvider:
    return BinanceSpotProvider(
        base_url=settings.binance_spot_base_url,
        timeout_seconds=settings.http_timeout_seconds,
    )


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name, "environment": settings.app_env}


@app.get("/api/v1/markets/spot/scan", tags=["markets"])
async def spot_market_scan(
    quote_asset: str = Query(default="USDT", min_length=2, max_length=12),
    min_quote_volume: float = Query(default=0.0, ge=0.0),
) -> dict:
    result = await scan_spot_markets(
        get_spot_provider(),
        quote_asset=quote_asset,
        min_quote_volume=min_quote_volume,
    )
    if result["status"] == "FAILED":
        raise HTTPException(status_code=502, detail=result)
    return result


@app.get("/api/v1/markets/spot/klines/{symbol}", tags=["markets"])
async def spot_klines(
    symbol: str,
    interval: Literal[
        "1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h",
        "6h", "8h", "12h", "1d", "3d", "1w", "1M"
    ] = "1h",
    limit: int = Query(default=500, ge=1, le=1000),
) -> dict:
    try:
        rows = await get_spot_provider().klines(symbol, interval, limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail={"status": "FAILED", "error": str(exc)}) from exc
    return {
        "status": "COMPLETED",
        "source": "Binance Spot public REST API",
        "symbol": symbol.upper(),
        "interval": interval,
        "count": len(rows),
        "klines": rows,
    }
