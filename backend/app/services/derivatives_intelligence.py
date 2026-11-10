import asyncio
import math
from datetime import datetime, timezone
from typing import Any

from app.providers.binance_futures import BinanceFuturesProvider


def _float(value: Any) -> float | None:
    try:
        if isinstance(value, bool):
            return None
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError, OverflowError):
        return None


def summarize_order_book(book: dict[str, Any], levels: int = 20) -> dict[str, Any]:
    raw_bids = book.get("bids", [])
    raw_asks = book.get("asks", [])
    bids = raw_bids[:levels] if isinstance(raw_bids, list) else []
    asks = raw_asks[:levels] if isinstance(raw_asks, list) else []
    parsed_bids = [
        (_float(row[0]), _float(row[1]))
        for row in bids if isinstance(row, (list, tuple)) and len(row) >= 2
    ]
    parsed_asks = [
        (_float(row[0]), _float(row[1]))
        for row in asks if isinstance(row, (list, tuple)) and len(row) >= 2
    ]
    parsed_bids = [(p, q) for p, q in parsed_bids if p is not None and q is not None and p > 0 and q > 0]
    parsed_asks = [(p, q) for p, q in parsed_asks if p is not None and q is not None and p > 0 and q > 0]

    if not parsed_bids or not parsed_asks:
        return {
            "status": "INCOMPLETE",
            "levels_requested": levels,
            "bid_levels_received": len(parsed_bids),
            "ask_levels_received": len(parsed_asks),
            "best_bid": None,
            "best_ask": None,
            "spread": None,
            "spread_bps": None,
            "bid_notional": None,
            "ask_notional": None,
            "depth_imbalance": None,
            "note": "Insufficient valid bid/ask levels",
        }

    best_bid = parsed_bids[0][0]
    best_ask = parsed_asks[0][0]
    midpoint = (best_bid + best_ask) / 2 if best_bid + best_ask else None
    spread = best_ask - best_bid
    if best_ask <= best_bid:
        return {
            "status": "INCOMPLETE",
            "levels_requested": levels,
            "bid_levels_received": len(parsed_bids),
            "ask_levels_received": len(parsed_asks),
            "best_bid": best_bid,
            "best_ask": best_ask,
            "spread": None,
            "spread_bps": None,
            "bid_notional": None,
            "ask_notional": None,
            "depth_imbalance": None,
            "note": "Invalid or crossed order book; spread and depth metrics withheld.",
        }
    bid_notional = sum(price * quantity for price, quantity in parsed_bids)
    ask_notional = sum(price * quantity for price, quantity in parsed_asks)
    total = bid_notional + ask_notional

    return {
        "status": "COMPLETED",
        "levels_requested": levels,
        "bid_levels_received": len(parsed_bids),
        "ask_levels_received": len(parsed_asks),
        "best_bid": best_bid,
        "best_ask": best_ask,
        "mid_price": midpoint,
        "spread": spread,
        "spread_bps": (spread / midpoint * 10000) if midpoint else None,
        "bid_notional": bid_notional,
        "ask_notional": ask_notional,
        "depth_imbalance": ((bid_notional - ask_notional) / total) if total else None,
        "note": (
            "Snapshot only; visible depth excludes some order types and can change rapidly. "
            "Depth imbalance is not proof of buying or selling intent."
        ),
    }


async def _capture(name: str, awaitable: Any) -> dict[str, Any]:
    try:
        return {"status": "COMPLETED", "data": await awaitable}
    except Exception as exc:
        return {"status": "FAILED", "error": "UPSTREAM_UNAVAILABLE",
                "error_type": type(exc).__name__}


async def get_derivatives_intelligence(
    provider: BinanceFuturesProvider,
    symbol: str,
    period: str = "1h",
    history_limit: int = 30,
    order_book_limit: int = 100,
) -> dict[str, Any]:
    symbol = symbol.upper()
    if provider.market != "USD_M":
        raise ValueError("Derivatives intelligence currently supports USD_M only")

    tasks = {
        "funding_rate_history": provider.funding_rate(symbol, min(history_limit, 100)),
        "open_interest": provider.open_interest(symbol),
        "open_interest_history": provider.open_interest_history(
            symbol, period, min(history_limit, 500)
        ),
        "global_long_short_account_ratio": provider.global_long_short_ratio(
            symbol, period, min(history_limit, 500)
        ),
        "taker_buy_sell_ratio": provider.taker_long_short_ratio(
            symbol, period, min(history_limit, 500)
        ),
        "order_book": provider.order_book(symbol, order_book_limit),
    }
    names = list(tasks)
    values = await asyncio.gather(
        *[_capture(name, task) for name, task in tasks.items()]
    )
    sections = dict(zip(names, values))

    book_section = sections.get("order_book", {})
    if book_section.get("status") == "COMPLETED":
        book_data = book_section.pop("data")
        book_summary = summarize_order_book(book_data, levels=min(order_book_limit, 1000))
        sections["order_book"] = {
            "status": book_summary["status"],
            "data": book_summary,
            "last_update_id": book_data.get("lastUpdateId"),
            "event_time": book_data.get("E"),
            "transaction_time": book_data.get("T"),
        }

    failed_sections = [
        name for name, section in sections.items() if section.get("status") != "COMPLETED"
    ]
    return {
        "status": "COMPLETED" if not failed_sections else "INCOMPLETE",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "Binance USD-M Futures public REST API",
        "market": "USD_M",
        "symbol": symbol,
        "period": period,
        "failed_sections": failed_sections,
        "sections": sections,
        "interpretation_warnings": [
            "Global long/short account ratio represents account counts, not position size.",
            "Taker buy/sell ratio describes aggressive trade volume, not a guaranteed price direction.",
            "Open interest rising alone does not identify whether new positions are long or short.",
            "Funding rate is a periodic payment metric; positive or negative values are not standalone trade signals.",
            "Order book depth is a point-in-time snapshot and may change or be cancelled.",
        ],
    }
