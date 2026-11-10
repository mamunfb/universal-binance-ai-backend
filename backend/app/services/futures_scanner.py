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
        try:
            book_tickers = await provider.all_book_tickers()
            book_ticker_error = None
        except Exception as exc:
            book_tickers = []
            book_ticker_error = type(exc).__name__
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
    book_by_symbol = {item.get("symbol"): item for item in book_tickers if isinstance(item, dict) and item.get("symbol")}
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
        status = str(item.get("status") or item.get("contractStatus") or "UNKNOWN")
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
        quote_volume_method = "EXCHANGE_QUOTE_VOLUME"
        book = book_by_symbol.get(symbol)
        bid = _number(book.get("bidPrice")) if book else None
        ask = _number(book.get("askPrice")) if book else None
        mid = (bid + ask) / 2 if bid is not None and ask is not None and bid > 0 and ask >= bid else None
        spread_bps = ((ask - bid) / mid * 10000) if mid else None
        high_price = _number(ticker.get("highPrice"))
        low_price = _number(ticker.get("lowPrice"))
        range_24h_pct = ((high_price - low_price) / last_price * 100) if high_price is not None and low_price is not None and last_price else None
        if quote_volume is None and provider.market == "COIN_M":
            # COIN-M 24h ticker exposes baseVolume rather than quoteVolume.
            # Convert using the observed last price and label it as a derived notional.
            base_volume = _number(ticker.get("baseVolume"))
            if base_volume is not None and base_volume >= 0:
                quote_volume = base_volume * last_price if last_price is not None else None
                quote_volume_method = "DERIVED_BASE_VOLUME_TIMES_LAST_PRICE"
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
            "onboard_date_ms": info.get("onboardDate"),
            "onboard_date": (
                datetime.fromtimestamp(_number(info.get("onboardDate")) / 1000, timezone.utc).isoformat()
                if _number(info.get("onboardDate")) and _number(info.get("onboardDate")) > 0 else None
            ),
            "last_price": last_price, "price_change_percent_24h": change_pct,
            "quote_volume_24h": quote_volume, "quote_volume_method": quote_volume_method,
            "best_bid": bid, "best_ask": ask, "spread_bps": spread_bps,
            "range_24h_pct": range_24h_pct,
            "status": info.get("status") or info.get("contractStatus"),
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
    now_ms = datetime.now(timezone.utc).timestamp() * 1000
    newly_listed_contracts = [
        {"symbol": row["symbol"], "market": row["market"], "contract_type": row["contract_type"],
         "onboard_date": row["onboard_date"]}
        for row in results
        if row.get("onboard_date")
        and 0 <= now_ms - datetime.fromisoformat(row["onboard_date"]).timestamp() * 1000 <= 30 * 24 * 60 * 60 * 1000
    ]
    eligible_count = len(eligible)
    failed_status = "COMPLETED" if failed == 0 else "INCOMPLETE"
    return {
        "status": failed_status, "phase_status": "INCOMPLETE", "generated_at": generated_at,
        "source": f"Binance {provider.market} public REST API", "market": provider.market,
        "quote_asset_filter": quote, "perpetual_only": perpetual_only,
        "total_available_contracts": len(all_contracts),
        "eligible_symbols": eligible_count, "scanned_symbols": eligible_count - failed,
        "matched_symbols": len(results), "failed_symbols": failed,
        "excluded_contract_counts": excluded, "min_quote_volume": minimum_volume,
        "newly_listed_contracts_30d": newly_listed_contracts,
        "risk_tag_coverage": "UNAVAILABLE_FROM_THIS_EXCHANGE_INFO_SCAN",
        "unique_underlying_count": len(unique), "unique_underlyings": unique,
        "results": results,
        "stage1_metrics": {
            "best_bid_ask_spread": "AVAILABLE_FOR_RETURNED_BOOK_TICKERS" if book_by_symbol else "UNAVAILABLE",
            "24h_high_low_range_proxy": "AVAILABLE" if any(row.get("range_24h_pct") is not None for row in results) else "UNAVAILABLE",
            "order_book_depth": "NOT_COLLECTED_FOR_ALL_CONTRACTS",
            "volume_surge_vs_recent_average": "NOT_COLLECTED",
            "relative_strength_vs_btc": "NOT_COLLECTED",
            "market_cap": "NOT_COLLECTED",
            "funding_rate_open_interest_basis": "NOT_COLLECTED_FOR_ALL_CONTRACTS",
        },
        "stage1_missing_metrics": [
            "order_book_depth", "volume_surge_vs_recent_average", "relative_strength_vs_btc",
            "market_cap", "funding_rate_open_interest_basis",
        ],
        "book_ticker_error": book_ticker_error,
        "coverage_warning": (
            "This scans one Futures market family (USD_M or COIN_M) per request. "
            "Funding, open interest, order-book depth, spread, mark/index price and leverage tiers "
            "are not enriched for every scanned contract by this Stage-1 endpoint."
        ),
    }
