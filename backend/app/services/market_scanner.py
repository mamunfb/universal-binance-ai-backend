from datetime import datetime, timezone
from typing import Any

from app.providers.binance_spot import BinanceSpotProvider

_STABLECOIN_ASSETS = {"USDT", "USDC", "FDUSD", "TUSD", "USDP", "DAI", "BUSD", "USTC", "USDE"}
_FIAT_ASSETS = {"USD", "EUR", "GBP", "AUD", "BRL", "TRY", "RUB", "UAH", "BIDR", "IDRT", "NGN", "ZAR", "PLN", "RON", "ARS", "JPY", "MXN", "VND", "CZK"}
_LEVERAGED_SUFFIXES = ("UP", "DOWN", "BULL", "BEAR")


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
    """Scan all eligible Spot symbols; omitted quote_asset means all quote assets."""
    generated_at = datetime.now(timezone.utc).isoformat()
    quote = quote_asset.strip().upper() if quote_asset and quote_asset.strip() else None
    minimum_volume = _number(min_quote_volume)
    if minimum_volume is None or minimum_volume < 0 or isinstance(min_quote_volume, bool):
        return {
            "status": "FAILED", "phase_status": "FAILED", "generated_at": generated_at,
            "source": "Binance Spot public REST API", "market": "SPOT",
            "quote_asset_filter": quote, "error_code": "INVALID_FILTER",
            "error": "min_quote_volume must be a finite non-negative number", "results": [],
            "total_available_pairs": 0, "eligible_symbols": 0, "scanned_symbols": 0,
            "matched_symbols": 0, "failed_symbols": 0, "unique_coin_count": 0, "unique_coins": [],
        }

    try:
        exchange_info, tickers, book_tickers, book_error = await _fetch_inputs(provider)
    except Exception as exc:
        return {
            "status": "FAILED", "phase_status": "FAILED", "generated_at": generated_at,
            "source": "Binance Spot public REST API", "market": "SPOT",
            "quote_asset_filter": quote, "total_available_pairs": 0,
            "eligible_symbols": 0, "scanned_symbols": 0, "matched_symbols": 0,
            "failed_symbols": 0, "error": str(exc), "results": [],
            "unique_coin_count": 0, "unique_coins": [],
        }

    if not isinstance(exchange_info, dict) or not isinstance(exchange_info.get("symbols"), list) or not isinstance(tickers, list):
        return {
            "status": "FAILED", "phase_status": "FAILED", "generated_at": generated_at,
            "source": "Binance Spot public REST API", "market": "SPOT",
            "quote_asset_filter": quote, "error_code": "UPSTREAM_INVALID_RESPONSE",
            "error": "Binance returned an unexpected Spot market-data response", "results": [],
            "total_available_pairs": 0, "eligible_symbols": 0, "scanned_symbols": 0,
            "matched_symbols": 0, "failed_symbols": 0, "unique_coin_count": 0, "unique_coins": [],
        }
    symbols = exchange_info["symbols"]
    ticker_by_symbol = {
        item.get("symbol"): item for item in tickers
        if isinstance(item, dict) and item.get("symbol")
    }
    book_by_symbol = {
        item.get("symbol"): item for item in book_tickers
        if isinstance(item, dict) and item.get("symbol")
    }
    btc_change = _number(ticker_by_symbol.get("BTCUSDT", {}).get("priceChangePercent"))
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
        base_asset = str(item.get("baseAsset") or "").upper()
        quote_asset_code = str(item.get("quoteAsset") or "").upper()
        if base_asset in _STABLECOIN_ASSETS and quote_asset_code in _STABLECOIN_ASSETS:
            excluded["STABLECOIN_VS_STABLECOIN"] = excluded.get("STABLECOIN_VS_STABLECOIN", 0) + 1
            continue
        if base_asset in _FIAT_ASSETS or quote_asset_code in _FIAT_ASSETS:
            excluded["FIAT_PAIR"] = excluded.get("FIAT_PAIR", 0) + 1
            continue
        if base_asset.endswith(_LEVERAGED_SUFFIXES):
            excluded["LEVERAGED_TOKEN"] = excluded.get("LEVERAGED_TOKEN", 0) + 1
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
        high_price = _number(ticker.get("highPrice"))
        low_price = _number(ticker.get("lowPrice"))
        book = book_by_symbol.get(symbol)
        bid = _number(book.get("bidPrice")) if book else None
        ask = _number(book.get("askPrice")) if book else None
        mid = (bid + ask) / 2 if bid is not None and ask is not None and bid > 0 and ask >= bid else None
        spread_bps = ((ask - bid) / mid * 10000) if mid else None
        range_24h_pct = ((high_price - low_price) / last_price * 100) if high_price is not None and low_price is not None and last_price else None
        if quote_volume is None or quote_volume < 0 or last_price is None or last_price <= 0 or change_pct is None:
            failed += 1
            continue
        if quote_volume < minimum_volume:
            continue
        onboard_ms = _number(info.get("onboardDate"))
        onboard_at = datetime.fromtimestamp(onboard_ms / 1000, timezone.utc).isoformat() if onboard_ms and onboard_ms > 0 else None
        results.append({
            "symbol": symbol, "base_asset": info.get("baseAsset"), "onboard_date": onboard_at,
            "quote_asset": info.get("quoteAsset"), "last_price": last_price,
            "price_change_percent_24h": change_pct, "quote_volume_24h": quote_volume,
            "best_bid": bid, "best_ask": ask, "spread_bps": spread_bps,
            "range_24h_pct": range_24h_pct,
            "relative_strength_vs_btc_24h_pp": change_pct - btc_change if btc_change is not None else None,
            "status": info.get("status"), "allowed_order_types": info.get("orderTypes", []),
            "filters": info.get("filters", []),
        })

    results.sort(key=lambda row: (str(row.get("quote_asset") or ""), -row["quote_volume_24h"]))
    grouped_by_base: dict[str, list[dict[str, Any]]] = {}
    for row in results:
        grouped_by_base.setdefault(str(row.get("base_asset") or row["symbol"]), []).append(row)
    unique_coins = []
    for base, rows in sorted(grouped_by_base.items()):
        quote_assets = {str(row.get("quote_asset") or "") for row in rows}
        comparable = len(quote_assets) == 1
        provisional = max(rows, key=lambda row: row["quote_volume_24h"]) if comparable else None
        unique_coins.append({
            "base_asset": base,
            "primary_symbol": provisional["symbol"] if provisional else None,
            "primary_quote_asset": provisional["quote_asset"] if provisional else None,
            "primary_quote_volume_24h": provisional["quote_volume_24h"] if provisional else None,
            "candidate_symbols": [row["symbol"] for row in rows],
            "primary_selection_status": (
                "PROVISIONAL_QUOTE_VOLUME_ONLY_DEPTH_NOT_CHECKED" if provisional
                else "NOT_ESTABLISHED_DIFFERENT_QUOTE_ASSETS_NOT_COMPARABLE"
            ),
        })
    now_ms = datetime.now(timezone.utc).timestamp() * 1000
    newly_listed_pairs = [
        {"symbol": row["symbol"], "base_asset": row["base_asset"], "onboard_date": row["onboard_date"]}
        for row in results
        if row.get("onboard_date")
        and 0 <= now_ms - datetime.fromisoformat(row["onboard_date"]).timestamp() * 1000 <= 30 * 24 * 60 * 60 * 1000
    ]
    scanned = len(eligible)
    return {
        "status": "COMPLETED" if failed == 0 else "INCOMPLETE",
        "phase_status": "INCOMPLETE",
        "generated_at": generated_at, "source": "Binance Spot public REST API",
        "market": "SPOT", "quote_asset_filter": quote,
        "total_available_pairs": len(symbols), "eligible_symbols": scanned,
        "scanned_symbols": scanned - failed, "matched_symbols": len(results),
        "failed_symbols": failed, "excluded_pair_counts": excluded,
        "min_quote_volume": minimum_volume, "unique_coin_count": len(unique_coins),
        "unique_coins": unique_coins, "results": results,
        "newly_listed_pairs_30d": newly_listed_pairs,
        "risk_tag_coverage": "UNAVAILABLE_FROM_THIS_EXCHANGE_INFO_SCAN",
        "stage1_metrics": {
            "best_bid_ask_spread": "AVAILABLE_FOR_RETURNED_BOOK_TICKERS" if book_by_symbol else "UNAVAILABLE",
            "24h_high_low_range_proxy": "AVAILABLE" if any(row["range_24h_pct"] is not None for row in results) else "UNAVAILABLE",
            "relative_strength_vs_btc_24h": "AVAILABLE" if btc_change is not None else "UNAVAILABLE",
            "order_book_depth": "NOT_COLLECTED_FOR_ALL_PAIRS",
            "volume_surge_vs_recent_average": "NOT_COLLECTED",
            "market_cap": "NOT_COLLECTED",
        },
        "stage1_missing_metrics": ["order_book_depth", "volume_surge_vs_recent_average", "market_cap"],
        "book_ticker_error": book_error,
        "coverage_warning": (
            "This is a complete eligible-symbol/ticker pass only. Full Stage 1 remains INCOMPLETE: "
            "depth, recent-average volume surge and market-cap enrichment are not collected for every pair. "
            "Unique-pair choice is provisional because raw quote volumes across different quote assets are not comparable."
        ),
    }


async def _fetch_inputs(provider: BinanceSpotProvider) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], str | None]:
    import asyncio
    exchange_info, tickers = await asyncio.gather(provider.exchange_info(), provider.all_24h_tickers())
    try:
        books = await provider.all_book_tickers()
        return exchange_info, tickers, books, None
    except Exception as exc:
        return exchange_info, tickers, [], type(exc).__name__
