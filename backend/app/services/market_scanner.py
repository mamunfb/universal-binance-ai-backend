from datetime import datetime, timezone
from typing import Any

from app.providers.binance_spot import BinanceSpotProvider


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


async def scan_spot_markets(
    provider: BinanceSpotProvider,
    quote_asset: str = "USDT",
    min_quote_volume: float = 0.0,
) -> dict[str, Any]:
    """Scan all returned Spot symbols for one quote asset; report coverage honestly."""
    generated_at = datetime.now(timezone.utc).isoformat()
    quote_asset = quote_asset.upper()

    try:
        exchange_info, tickers = await _fetch_inputs(provider)
    except Exception as exc:
        return {
            "status": "FAILED",
            "generated_at": generated_at,
            "source": "Binance Spot public REST API",
            "market": "SPOT",
            "quote_asset": quote_asset,
            "eligible_symbols": 0,
            "scanned_symbols": 0,
            "matched_symbols": 0,
            "failed_symbols": 0,
            "error": str(exc),
            "results": [],
        }

    eligible = [
        item for item in exchange_info["symbols"]
        if item.get("status") == "TRADING"
        and item.get("quoteAsset") == quote_asset
        and item.get("isSpotTradingAllowed", True)
    ]
    ticker_by_symbol = {
        item.get("symbol"): item for item in tickers if item.get("symbol")
    }

    results: list[dict[str, Any]] = []
    failed = 0
    for symbol_info in eligible:
        symbol = symbol_info.get("symbol")
        ticker = ticker_by_symbol.get(symbol)
        if ticker is None:
            failed += 1
            continue

        quote_volume = _number(ticker.get("quoteVolume"))
        last_price = _number(ticker.get("lastPrice"))
        change_pct = _number(ticker.get("priceChangePercent"))
        if quote_volume is None or last_price is None or change_pct is None:
            failed += 1
            continue
        if quote_volume < min_quote_volume:
            continue

        results.append({
            "symbol": symbol,
            "base_asset": symbol_info.get("baseAsset"),
            "quote_asset": symbol_info.get("quoteAsset"),
            "last_price": last_price,
            "price_change_percent_24h": change_pct,
            "quote_volume_24h": quote_volume,
            "status": symbol_info.get("status"),
        })

    results.sort(key=lambda row: row["quote_volume_24h"], reverse=True)
    scanned = len(eligible)
    return {
        "status": "COMPLETED" if failed == 0 else "INCOMPLETE",
        "generated_at": generated_at,
        "source": "Binance Spot public REST API",
        "market": "SPOT",
        "quote_asset": quote_asset,
        "eligible_symbols": scanned,
        "scanned_symbols": scanned - failed,
        "matched_symbols": len(results),
        "failed_symbols": failed,
        "min_quote_volume": min_quote_volume,
        "results": results,
    }


async def _fetch_inputs(provider: BinanceSpotProvider) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    import asyncio

    return await asyncio.gather(provider.exchange_info(), provider.all_24h_tickers())
