import asyncio
import math
from datetime import datetime, timezone
from typing import Any

from app.providers.binance_spot import BinanceSpotProvider
from app.providers.binance_futures import BinanceFuturesProvider


def _positive_price(value: Any) -> float | None:
    try:
        if isinstance(value, bool):
            return None
        parsed = float(value)
        return parsed if math.isfinite(parsed) and parsed > 0 else None
    except (TypeError, ValueError, OverflowError):
        return None


def _funding_snapshot(rows: Any) -> dict[str, Any]:
    if not isinstance(rows, list) or not rows:
        return {"status": "INCOMPLETE", "error": "NO_FUNDING_HISTORY"}
    latest = rows[-1]
    if not isinstance(latest, dict):
        return {"status": "INCOMPLETE", "error": "MALFORMED_FUNDING_HISTORY"}
    try:
        rate = float(latest["fundingRate"])
        funding_time = int(latest["fundingTime"])
    except (KeyError, TypeError, ValueError, OverflowError):
        return {"status": "INCOMPLETE", "error": "MALFORMED_FUNDING_HISTORY"}
    if not math.isfinite(rate) or funding_time <= 0:
        return {"status": "INCOMPLETE", "error": "INVALID_FUNDING_VALUE"}
    return {
        "status": "COMPLETED",
        "funding_rate": rate,
        "funding_time_ms": funding_time,
        "source": "Binance USD-M Futures funding rate history",
        "note": "Funding is a periodic payment rate, not a guaranteed directional signal.",
    }


async def analyze_spot_futures_basis(
    spot_provider: BinanceSpotProvider,
    futures_provider: BinanceFuturesProvider,
    symbol: str,
) -> dict[str, Any]:
    normalized = symbol.strip().upper() if isinstance(symbol, str) else ""
    if not normalized:
        raise ValueError("symbol must not be empty")
    if futures_provider.market != "USD_M":
        raise ValueError("Spot/Futures basis currently supports USD_M Futures only")

    spot_result, futures_result, funding_result = await asyncio.gather(
        _capture(spot_provider.price_ticker(normalized)),
        _capture(futures_provider.price_ticker(normalized)),
        _capture(futures_provider.funding_rate(normalized, 1)),
    )
    generated_at = datetime.now(timezone.utc).isoformat()

    if spot_result["status"] != "COMPLETED" or futures_result["status"] != "COMPLETED":
        return {
            "status": "INCOMPLETE",
            "generated_at": generated_at,
            "symbol": normalized,
            "spot": spot_result,
            "futures": futures_result,
            "funding": _funding_snapshot(funding_result["data"])
            if funding_result["status"] == "COMPLETED"
            else {"status": "INCOMPLETE", "error": "FUNDING_UNAVAILABLE"},
            "error": "PRICE_SNAPSHOT_UNAVAILABLE",
        }

    spot_data = spot_result["data"]
    futures_data = futures_result["data"]
    spot_symbol = spot_data.get("symbol")
    futures_symbol = futures_data.get("symbol")
    spot_price = _positive_price(spot_data.get("price"))
    futures_price = _positive_price(futures_data.get("price"))
    if spot_symbol != normalized or futures_symbol != normalized or spot_price is None or futures_price is None:
        return {
            "status": "INCOMPLETE",
            "generated_at": generated_at,
            "symbol": normalized,
            "error": "INVALID_OR_MISMATCHED_PRICE_RESPONSE",
            "spot": {"status": "INCOMPLETE", "error": "INVALID_PRICE_RESPONSE"},
            "futures": {"status": "INCOMPLETE", "error": "INVALID_PRICE_RESPONSE"},
        }

    basis = futures_price - spot_price
    basis_percent = basis / spot_price * 100
    funding = (
        _funding_snapshot(funding_result["data"])
        if funding_result["status"] == "COMPLETED"
        else {"status": "INCOMPLETE", "error": "FUNDING_UNAVAILABLE"}
    )
    return {
        "status": "COMPLETED" if funding["status"] == "COMPLETED" else "INCOMPLETE",
        "generated_at": generated_at,
        "source": "Binance public Spot and USD-M Futures REST APIs",
        "symbol": normalized,
        "price_comparison": {
            "status": "COMPLETED",
            "spot_price": spot_price,
            "futures_price": futures_price,
            "basis": basis,
            "basis_percent": basis_percent,
            "relationship": "FUTURES_PREMIUM" if basis > 0 else "FUTURES_DISCOUNT" if basis < 0 else "AT_PARITY",
            "note": "Spot and Futures prices are independently fetched snapshots; small timing differences may affect the measured basis.",
        },
        "funding": funding,
        "interpretation_warnings": [
            "A positive or negative basis is descriptive and is not a standalone trading signal.",
            "Funding rate and basis are separate measurements and should not be treated as interchangeable.",
            "This endpoint does not place orders or estimate guaranteed returns.",
        ],
    }


async def _capture(awaitable: Any) -> dict[str, Any]:
    try:
        return {"status": "COMPLETED", "data": await awaitable}
    except Exception as exc:
        return {"status": "FAILED", "error": "UPSTREAM_UNAVAILABLE", "error_type": type(exc).__name__}
