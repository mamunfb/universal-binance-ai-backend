from datetime import datetime, timezone
from typing import Any

from app.providers.binance_spot import BinanceSpotProvider


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if number == number and abs(number) != float("inf") else None


async def scan_spot_markets(
    provider: BinanceSpotProvider,
    quote_asset: str | None = None,
    min_quote_volume: float = 0.0,
) -> dict[str, Any]:
    """Scan every returned eligible Spot symbol; an omitted quote scans all quote assets."""
    generated_at = datetime.now(timezone.utc).isoformat()
    quote = quote_asset.strip().upper() if quote_asset and quote_asset.strip() else None

    try:
        exchange_info, tickers = await _fetch_inputs(provider)
    except Exception as exc:
        return {
            "status": "FAILED", "generated_at": generated_at,
            "source": "Binance Spot public REST API", "market": "SPOT",
            "quote_asset_filter": quote, "total_available_pairs": 0,
            "eligible_symbols": 0, "scanned_symbols": 0, "matched_symbols": 0,
            "failed_symbols": 0, "error": str(exc), "results": [],
            "unique_coin_count": 0, "unique_coins": [],
        }

    symbols = exchange_info["symbols"]
    ticker_by_symbol = {
        item.get("symbol"): item for item in tickers
        if isinstance(item, dict) and item.get("symbol")
    }
    excluded: dict[str, int] = {}
    eligible: list[dict[str, Any]] = []
    for item in symbols:
        if not isinstance(item, dict):
            excluded["INVALID_EXCHANGE_INFO_ROW"] = excluded.get("INVALID_EXCHANGE_INFO_ROW", 0) + 1
            continue
        status = str(item.get("status") or "UNKNOWN")
        if status != "TRADING":
            excluded[status] = excluded.get(status, 0) + 1
            continue
        if not item.get("isSpotTradingAllowed", True):
            excluded["SPOT_TRADING_NOT_ALLOWED"] = excluded.get("SPOT_TRADING_NOT_ALLOWED", 0) + 1
            continue
        if quote and item.get("quoteAsset") != quote:
            excluded["QUOTE_ASSET_FILTERED"] = excluded.get("QUOTE_ASSET_FILTERED", 0) + 1
            continue
        eligible.append(item)

    results: list[dict[str, Any]] = []
    failed = 0
    for info in eligible:
        symbol = info.get("symbol")
        ticker = ticker_by_symbol.get(symbol)
        if ticker is None:
            failed += 1
            continue
        quote_volume = _number(ticker.get("quoteVolume"))
        last_price = _number(ticker.get("lastPrice"))
        change_pct = _number(ticker.get("priceChangePercent"))
        if quote_volume is None or quote_volume < 0 or last_price is None or last_price <= 0 or change_pct is None:
            failed += 1
            continue
        if quote_volume < min_quote_volume:
            continue
        results.append({
            "symbol": symbol,
            "base_asset": info.get("baseAsset"),
            "quote_asset": info.get("quoteAsset"),
            "last_price": last_price,
            "price_change_percent_24h": change_pct,
            "quote_volume_24h": quote_volume,
            "status": info.get("status"),
            "allowed_order_types": info.get("orderTypes", []),
            "filters": info.get("filters", []),
        })

    results.sort(key=lambda row: row["quote_volume_24h"], reverse=True)
    primary_by_base: dict[str, dict[str, Any]] = {}
    for row in results:
        primary_by_base.setdefault(str(row.get("base_asset") or row["symbol"]), row)
    unique_coins = [
        {"base_asset": base, "primary_symbol": row["symbol"],
         "primary_quote_asset": row["quote_asset"],
         "primary_quote_volume_24h": row["quote_volume_24h"]}
        for base, row in sorted(primary_by_base.items())
    ]
    scanned = len(eligible)
    return {
        "status": "COMPLETED" if failed == 0 else "INCOMPLETE",
        "generated_at": generated_at,
        "source": "Binance Spot public REST API",
        "market": "SPOT",
        "quote_asset_filter": quote,
        "total_available_pairs": len(symbols),
        "eligible_symbols": scanned,
        "scanned_symbols": scanned - failed,
        "matched_symbols": len(results),
        "failed_symbols": failed,
        "excluded_pair_counts": excluded,
        "min_quote_volume": min_quote_volume,
        "unique_coin_count": len(unique_coins),
        "unique_coins": unique_coins,
        "results": results,
        "coverage_warning": (
            "All eligible symbols returned by exchangeInfo were checked against the bulk 24-hour ticker response. "
            "This scan does not yet enrich every pair with order-book depth, spread, volatility, or recent-average volume."
        ),
    }


async def _fetch_inputs(provider: BinanceSpotProvider) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    import asyncio
    return await asyncio.gather(provider.exchange_info(), provider.all_24h_tickers())
