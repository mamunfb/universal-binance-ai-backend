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
    provider: BinanceFuturesProvider, generated_at: str, quote: str | None,
    error_code: str, message: str,
) -> dict[str, Any]:
    return {
        "status": "FAILED", "generated_at": generated_at,
        "source": f"Binance {provider.market} public REST API",
        "market": provider.market, "quote_asset_filter": quote,
        "total_available_contracts": 0, "eligible_symbols": 0,
        "scanned_symbols": 0, "matched_symbols": 0, "failed_symbols": 0,
        "error_code": error_code, "error": message, "results": [],
        "unique_underlying_count": 0, "unique_underlyings": [],
    }


async def scan_futures_markets(
    provider: BinanceFuturesProvider,
    quote_asset: str | None = None,
    min_quote_volume: float = 0.0,
    perpetual_only: bool = False,
) -> dict[str, Any]:
    """Scan every eligible active contract in one Futures market family.

    By default this includes perpetual and currently trading dated contracts.
    Use quote_asset only when a deliberate narrowed scan is desired.
    """
    generated_at = datetime.now(timezone.utc).isoformat()
    quote = quote_asset.strip().upper() if quote_asset and quote_asset.strip() else None
    if quote_asset is not None and not quote:
        return _failed_result(provider, generated_at, quote, "INVALID_FILTER", "quote_asset must not be empty")
    minimum_volume = _number(min_quote_volume)
    if minimum_volume is None or minimum_volume < 0:
        return _failed_result(provider, generated_at, quote, "INVALID_FILTER", "min_quote_volume must be a finite non-negative number")

    try:
        exchange_info, tickers = await asyncio.gather(provider.exchange_info(), provider.all_24h_tickers())
    except Exception:
        return _failed_result(
            provider, generated_at, quote, "UPSTREAM_UNAVAILABLE",
            "Could not retrieve Futures exchange metadata and 24-hour tickers",
        )
    if not isinstance(exchange_info, dict) or not isinstance(exchange_info.get("symbols"), list) or not isinstance(tickers, list):
        return _failed_result(
            provider, generated_at, quote, "UPSTREAM_INVALID_RESPONSE",
            "Binance returned an unexpected Futures market-data response",
        )

    all_contracts = exchange_info["symbols"]
    ticker_by_symbol = {
        item.get("symbol"): item for item in tickers
        if isinstance(item, dict) and item.get("symbol")
    }
    excluded: dict[str, int] = {}
    eligible: list[dict[str, Any]] = []
    for item in all_contracts:
        if not isinstance(item, dict):
            excluded["INVALID_EXCHANGE_INFO_ROW"] = excluded.get("INVALID_EXCHANGE_INFO_ROW", 0) + 1
            continue
        status = str(item.get("status") or "UNKNOWN")
        if status != "TRADING":
            excluded[status] = excluded.get(status, 0) + 1
            continue
        if quote and item.get("quoteAsset") != quote:
            excluded["QUOTE_ASSET_FILTERED"] = excluded.get("QUOTE_ASSET_FILTERED", 0) + 1
            continue
        if perpetual_only and item.get("contractType") != "PERPETUAL":
            excluded["DATED_CONTRACT_FILTERED"] = excluded.get("DATED_CONTRACT_FILTERED", 0) + 1
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
        last_price = _number(ticker.get("lastPrice"))
        change_pct = _number(ticker.get("priceChangePercent"))
        quote_volume = _number(ticker.get("quoteVolume"))
        if last_price is None or last_price <= 0 or change_pct is None or quote_volume is None or quote_volume < 0:
            failed += 1
            continue
        if quote_volume < minimum_volume:
            continue
        results.append({
            "market": provider.market, "symbol": symbol,
            "base_asset": info.get("baseAsset"), "quote_asset": info.get("quoteAsset"),
            "margin_asset": info.get("marginAsset"), "contract_type": info.get("contractType"),
            "delivery_date": info.get("deliveryDate"),
            "onboard_date": info.get("onboardDate"),
            "last_price": last_price, "price_change_percent_24h": change_pct,
            "quote_volume_24h": quote_volume, "status": info.get("status"),
            "filters": info.get("filters", []),
        })

    results.sort(key=lambda row: row["quote_volume_24h"], reverse=True)
    primary: dict[str, dict[str, Any]] = {}
    for row in results:
        primary.setdefault(str(row.get("base_asset") or row["symbol"]), row)
    unique = [
        {"base_asset": base, "primary_symbol": row["symbol"],
         "market": row["market"], "contract_type": row["contract_type"],
         "margin_asset": row["margin_asset"], "quote_volume_24h": row["quote_volume_24h"]}
        for base, row in sorted(primary.items())
    ]
    eligible_count = len(eligible)
    failed_status = "COMPLETED" if failed == 0 else "INCOMPLETE"
    return {
        "status": failed_status, "generated_at": generated_at,
        "source": f"Binance {provider.market} public REST API", "market": provider.market,
        "quote_asset_filter": quote, "perpetual_only": perpetual_only,
        "total_available_contracts": len(all_contracts),
        "eligible_symbols": eligible_count, "scanned_symbols": eligible_count - failed,
        "matched_symbols": len(results), "failed_symbols": failed,
        "excluded_contract_counts": excluded, "min_quote_volume": minimum_volume,
        "unique_underlying_count": len(unique), "unique_underlyings": unique,
        "results": results,
        "coverage_warning": (
            "This scans one Futures market family (USD_M or COIN_M) per request. "
            "Funding, open interest, order-book depth, spread, mark/index price and leverage tiers "
            "are not enriched for every scanned contract by this Stage-1 endpoint."
        ),
    }
