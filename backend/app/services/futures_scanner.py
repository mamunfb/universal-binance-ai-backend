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
        try:
            premium_payload = await provider.premium_index()
            premium_rows = premium_payload if isinstance(premium_payload, list) else [premium_payload]
            premium_error = None
        except Exception as exc:
            premium_rows = []
            premium_error = type(exc).__name__
        try:
            funding_info_rows = await provider.funding_info()
            funding_info_error = None
        except Exception as exc:
            funding_info_rows = []
            funding_info_error = type(exc).__name__
    except Exception as exc:
        if isinstance(exc, httpx.HTTPStatusError):
            status_code = exc.response.status_code
            error_code = f"HTTP_{status_code}"
            message = (
                f"Binance {provider.market} returned HTTP {status_code} "
                f"for {exc.request.url}. Response: {exc.response.text[:500]}"
            )
        else:
            error_code = "UPSTREAM_UNAVAILABLE"
            message = f"{type(exc).__name__}: {exc}"
        return _failed_result(provider, generated_at, quote, error_code, message)
    if not isinstance(exchange_info, dict) or not isinstance(exchange_info.get("symbols"), list) or not isinstance(tickers, list):
        return _failed_result(
            provider, generated_at, quote, "UPSTREAM_INVALID_RESPONSE",
            "Binance returned an unexpected Futures market-data response",
        )

    all_contracts = exchange_info["symbols"]
    book_by_symbol = {item.get("symbol"): item for item in book_tickers if isinstance(item, dict) and item.get("symbol")}
    premium_by_symbol = {item.get("symbol"): item for item in premium_rows if isinstance(item, dict) and item.get("symbol")}
    funding_info_by_symbol = {item.get("symbol"): item for item in funding_info_rows if isinstance(item, dict) and item.get("symbol")}
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
        premium = premium_by_symbol.get(symbol, {})
        funding_meta = funding_info_by_symbol.get(symbol, {})
        mark_price = _number(premium.get("markPrice"))
        index_price = _number(premium.get("indexPrice"))
        basis_bps = ((mark_price - index_price) / index_price * 10000) if mark_price is not None and index_price is not None and index_price > 0 else None
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
            "mark_price": mark_price, "index_price": index_price,
            "mark_index_basis_bps": basis_bps,
            "funding_rate": _number(premium.get("lastFundingRate")),
            "next_funding_time_ms": premium.get("nextFundingTime"),
            "funding_interval_hours": _number(funding_meta.get("fundingIntervalHours")),
            "status": info.get("status") or info.get("contractStatus"),
            "filters": info.get("filters", []),
        })

    results.sort(key=lambda row: (str(row.get("quote_asset") or ""), -row["quote_volume_24h"]))
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in results:
        grouped.setdefault(str(row.get("base_asset") or row["symbol"]), []).append(row)
    unique = []
    for base, rows in sorted(grouped.items()):
        quote_assets = {str(row.get("quote_asset") or "") for row in rows}
        margin_assets = {str(row.get("margin_asset") or "") for row in rows}
        comparable = len(quote_assets) == 1 and len(margin_assets) == 1
        selected = max(rows, key=lambda row: row["quote_volume_24h"]) if comparable else None
        unique.append({
            "base_asset": base,
            "primary_symbol": selected["symbol"] if selected else None,
            "market": provider.market,
            "contract_type": selected["contract_type"] if selected else None,
            "margin_asset": selected["margin_asset"] if selected else None,
            "quote_asset": selected["quote_asset"] if selected else None,
            "quote_volume_24h": selected["quote_volume_24h"] if selected else None,
            "candidate_symbols": [row["symbol"] for row in rows],
            "primary_selection_status": (
                "PROVISIONAL_QUOTE_VOLUME_ONLY_DEPTH_NOT_CHECKED" if selected
                else "NOT_ESTABLISHED_INCOMPARABLE_QUOTE_OR_MARGIN_ASSETS"
            ),
        })
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
            "funding_rate": "AVAILABLE" if premium_by_symbol else "UNAVAILABLE",
            "mark_index_basis": "AVAILABLE" if premium_by_symbol else "UNAVAILABLE",
            "funding_interval_hours": "AVAILABLE_FOR_RETURNED_OVERRIDE_ROWS" if funding_info_by_symbol else "UNAVAILABLE_OR_NO_OVERRIDE_ROWS",
            "open_interest_and_change": "NOT_COLLECTED_FOR_ALL_CONTRACTS",
        },
        "stage1_missing_metrics": [
            "order_book_depth", "volume_surge_vs_recent_average", "relative_strength_vs_btc",
            "market_cap", "open_interest_and_change",
        ],
        "book_ticker_error": book_ticker_error,
        "premium_index_error": premium_error,
        "funding_info_error": funding_info_error,
        "coverage_warning": (
            "This scans one Futures market family (USD_M or COIN_M) per request. "
            "Funding, open interest, order-book depth, spread, mark/index price and leverage tiers "
            "are not enriched for every scanned contract by this Stage-1 endpoint."
        ),
    }
