import asyncio
from datetime import datetime, timezone
from typing import Any

from app.providers.binance_futures import BinanceFuturesProvider


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


async def scan_futures_markets(
    provider: BinanceFuturesProvider,
    quote_asset: str | None = None,
    min_quote_volume: float = 0.0,
    perpetual_only: bool = True,
) -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).isoformat()
    quote = quote_asset.upper() if quote_asset else None

    try:
        exchange_info, tickers = await asyncio.gather(
            provider.exchange_info(), provider.all_24h_tickers()
        )
    except Exception as exc:
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
            "error": str(exc),
            "results": [],
        }

    eligible = []
    for item in exchange_info["symbols"]:
        if item.get("status") != "TRADING":
            continue
        if quote and item.get("quoteAsset") != quote:
            continue
        if perpetual_only and item.get("contractType") != "PERPETUAL":
            continue
        eligible.append(item)

    ticker_by_symbol = {
        item.get("symbol"): item for item in tickers if item.get("symbol")
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
        if last_price is None or change_pct is None or quote_volume is None:
            failed += 1
            continue
        if quote_volume < min_quote_volume:
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
        "min_quote_volume": min_quote_volume,
        "results": results,
    }
