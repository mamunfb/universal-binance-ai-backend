import asyncio
import math
from datetime import datetime, timezone
from typing import Any

from app.providers.binance_futures import BinanceFuturesProvider


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _failed_result(
    provider: BinanceFuturesProvider,
    generated_at: str,
    quote: str | None,
    error_code: str,
    message: str,
) -> dict[str, Any]:
    return {
        "status": "FAILED",
        "generated_at": generated_at,
        "source": f"Binance {provider.market} public REST API",
        "market": provider.market,
        "quote_asset_filter": quote,
        "eligible_symbols": 0,
        "scanned_symbols": 0,
        "matched_symbols": 0,
        "failed_symbols": 0,
        "error_code": error_code,
        "error": message,
        "results": [],
    }


async def scan_futures_markets(
    provider: BinanceFuturesProvider,
    quote_asset: str | None = None,
    min_quote_volume: float = 0.0,
    perpetual_only: bool = True,
) -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).isoformat()
    quote = quote_asset.strip().upper() if quote_asset and quote_asset.strip() else None

    if quote_asset is not None and not quote:
        return _failed_result(
            provider, generated_at, quote, "INVALID_FILTER", "quote_asset must not be empty"
        )
    minimum_volume = _number(min_quote_volume)
    if minimum_volume is None or minimum_volume < 0:
        return _failed_result(
            provider,
            generated_at,
            quote,
            "INVALID_FILTER",
            "min_quote_volume must be a finite non-negative number",
        )

    try:
        exchange_info, tickers = await asyncio.gather(
            provider.exchange_info(), provider.all_24h_tickers()
        )
    except Exception:
        return _failed_result(
            provider,
            generated_at,
            quote,
            "UPSTREAM_UNAVAILABLE",
            "Could not retrieve Futures exchange metadata and 24-hour tickers",
        )

    if (
        not isinstance(exchange_info, dict)
        or not isinstance(exchange_info.get("symbols"), list)
        or not isinstance(tickers, list)
    ):
        return _failed_result(
            provider,
            generated_at,
            quote,
            "UPSTREAM_INVALID_RESPONSE",
            "Binance returned an unexpected Futures market-data response",
        )

    eligible = []
    for item in exchange_info["symbols"]:
        if not isinstance(item, dict):
            continue
        if item.get("status") != "TRADING":
            continue
        if quote and item.get("quoteAsset") != quote:
            continue
        if perpetual_only and item.get("contractType") != "PERPETUAL":
            continue
        eligible.append(item)

    ticker_by_symbol = {
        item.get("symbol"): item
        for item in tickers
        if isinstance(item, dict) and item.get("symbol")
    }
    results: list[dict[str, Any]] = []
    failed = 0

    for info in eligible:
        symbol = info.get("symbol")
        ticker = ticker_by_symbol.get(symbol)
        if ticker is None:
            failed += 1
            continue
        last_price = _number(ticker.get("lastPrice"))
        change_pct = _number(ticker.get("priceChangePercent"))
        quote_volume = _number(ticker.get("quoteVolume"))
        if (
            last_price is None
            or last_price <= 0
            or change_pct is None
            or quote_volume is None
            or quote_volume < 0
        ):
            failed += 1
            continue
        if quote_volume < minimum_volume:
            continue
        results.append({
            "market": provider.market,
            "symbol": symbol,
            "base_asset": info.get("baseAsset"),
            "quote_asset": info.get("quoteAsset"),
            "margin_asset": info.get("marginAsset"),
            "contract_type": info.get("contractType"),
            "last_price": last_price,
            "price_change_percent_24h": change_pct,
            "quote_volume_24h": quote_volume,
            "status": info.get("status"),
        })

    results.sort(key=lambda row: row["quote_volume_24h"], reverse=True)
    eligible_count = len(eligible)
    scanned_count = eligible_count - failed
    return {
        "status": "COMPLETED" if failed == 0 else "INCOMPLETE",
        "generated_at": generated_at,
        "source": f"Binance {provider.market} public REST API",
        "market": provider.market,
        "quote_asset_filter": quote,
        "perpetual_only": perpetual_only,
        "eligible_symbols": eligible_count,
        "scanned_symbols": scanned_count,
        "matched_symbols": len(results),
        "failed_symbols": failed,
        "min_quote_volume": minimum_volume,
        "results": results,
    }
