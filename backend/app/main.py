from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Literal

from fastapi import FastAPI, HTTPException, Query

from app.config import settings
from app.indicators import calculate_indicators
from app.providers.binance_spot import BinanceSpotProvider
from app.providers.binance_futures import BinanceFuturesProvider
from app.services.market_scanner import scan_spot_markets
from app.services.futures_scanner import scan_futures_markets
from app.services.derivatives_intelligence import get_derivatives_intelligence
from app.services.multi_timeframe import analyze_multiple_timeframes, analyze_btc_market_condition
from app.services.liquidation_collector import LiquidationCollector, LiquidationStore

liquidation_store = LiquidationStore(settings.liquidation_database_path)
liquidation_collector = LiquidationCollector(liquidation_store)


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.liquidation_collector_enabled:
        liquidation_collector.start()
    try:
        yield
    finally:
        if settings.liquidation_collector_enabled:
            await liquidation_collector.stop()


app = FastAPI(
    lifespan=lifespan,
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


def get_futures_provider(market: str) -> BinanceFuturesProvider:
    return BinanceFuturesProvider(market, timeout_seconds=settings.http_timeout_seconds)


@app.get("/api/v1/markets/futures/usdm/scan", tags=["markets"])
async def usdm_market_scan(
    quote_asset: str = Query(default="USDT", min_length=2, max_length=12),
    min_quote_volume: float = Query(default=0.0, ge=0.0),
    perpetual_only: bool = True,
) -> dict:
    result = await scan_futures_markets(
        get_futures_provider("USD_M"), quote_asset, min_quote_volume, perpetual_only
    )
    if result["status"] == "FAILED":
        raise HTTPException(status_code=502, detail=result)
    return result


@app.get("/api/v1/markets/futures/coinm/scan", tags=["markets"])
async def coinm_market_scan(
    quote_asset: str = Query(default="USD", min_length=2, max_length=12),
    min_quote_volume: float = Query(default=0.0, ge=0.0),
    perpetual_only: bool = True,
) -> dict:
    result = await scan_futures_markets(
        get_futures_provider("COIN_M"), quote_asset, min_quote_volume, perpetual_only
    )
    if result["status"] == "FAILED":
        raise HTTPException(status_code=502, detail=result)
    return result


@app.get("/api/v1/markets/futures/usdm/klines/{symbol}", tags=["markets"])
async def usdm_klines(
    symbol: str,
    interval: Literal[
        "1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h",
        "6h", "8h", "12h", "1d", "3d", "1w", "1M"
    ] = "1h",
    limit: int = Query(default=500, ge=1, le=1500),
) -> dict:
    try:
        rows = await get_futures_provider("USD_M").klines(symbol, interval, limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail={"status": "FAILED", "error": str(exc)}) from exc
    return {"status": "COMPLETED", "source": "Binance USD-M Futures public REST API",
            "symbol": symbol.upper(), "interval": interval, "count": len(rows), "klines": rows}


@app.get("/api/v1/markets/futures/coinm/klines/{symbol}", tags=["markets"])
async def coinm_klines(
    symbol: str,
    interval: Literal[
        "1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h",
        "6h", "8h", "12h", "1d", "3d", "1w", "1M"
    ] = "1h",
    limit: int = Query(default=500, ge=1, le=1500),
) -> dict:
    try:
        rows = await get_futures_provider("COIN_M").klines(symbol, interval, limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail={"status": "FAILED", "error": str(exc)}) from exc
    return {"status": "COMPLETED", "source": "Binance COIN-M Futures public REST API",
            "symbol": symbol.upper(), "interval": interval, "count": len(rows), "klines": rows}


@app.get("/api/v1/analysis/futures/usdm/derivatives/{symbol}", tags=["analysis"])
async def usdm_derivatives_intelligence(
    symbol: str,
    period: Literal["5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d"] = "1h",
    history_limit: int = Query(default=30, ge=1, le=100),
    order_book_limit: Literal[5, 10, 20, 50, 100, 500, 1000] = 100,
) -> dict:
    try:
        return await get_derivatives_intelligence(
            get_futures_provider("USD_M"),
            symbol=symbol,
            period=period,
            history_limit=history_limit,
            order_book_limit=order_book_limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail={"status": "FAILED", "error": str(exc)}) from exc


@app.get("/api/v1/analysis/spot/technical/{symbol}", tags=["analysis"])
async def spot_technical_analysis(
    symbol: str,
    interval: Literal[
        "1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h",
        "6h", "8h", "12h", "1d", "3d", "1w", "1M"
    ] = "1h",
    limit: int = Query(default=500, ge=2, le=1000),
) -> dict:
    try:
        rows = await get_spot_provider().klines(symbol, interval, limit)
        closes = [float(row[4]) for row in rows]
        indicators = calculate_indicators(closes)
    except Exception as exc:
        raise HTTPException(status_code=502, detail={"status": "FAILED", "error": str(exc)}) from exc
    return {
        "status": "COMPLETED",
        "source": "Binance Spot public REST API",
        "symbol": symbol.upper(),
        "interval": interval,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "indicators": indicators,
        "warning": "Indicators describe historical data and are not guaranteed trading signals.",
    }


@app.get("/api/v1/analysis/spot/multi-timeframe/{symbol}", tags=["analysis"])
async def spot_multi_timeframe_analysis(symbol: str) -> dict:
    return await analyze_multiple_timeframes(get_spot_provider(), symbol)


@app.get("/api/v1/analysis/market/btc-condition", tags=["analysis"])
async def btc_market_condition() -> dict:
    return await analyze_btc_market_condition(get_spot_provider())


@app.get("/api/v1/analysis/futures/liquidations/status", tags=["analysis"])
async def liquidation_collector_status() -> dict:
    if not settings.liquidation_collector_enabled:
        return {
            "status": "DISABLED",
            "collector_enabled": False,
            "message": "Set LIQUIDATION_COLLECTOR_ENABLED=true and run a persistent service to collect live events.",
            "stored_event_count": liquidation_store.count(),
        }
    return liquidation_collector.status()


@app.get("/api/v1/analysis/futures/liquidations/recent", tags=["analysis"])
async def recent_liquidations(
    symbol: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
) -> dict:
    rows = await __import__("asyncio").to_thread(
        liquidation_store.recent, symbol, limit
    )
    return {
        "status": "COMPLETED",
        "source": "Binance USDⓈ-M all-market forceOrder WebSocket snapshot stream",
        "symbol": symbol.upper() if symbol else None,
        "returned_count": len(rows),
        "events": rows,
        "coverage_warning": "Binance sends at most the latest liquidation snapshot per symbol per 1000ms. This is not a complete liquidation tape or historical exchange archive.",
    }


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
