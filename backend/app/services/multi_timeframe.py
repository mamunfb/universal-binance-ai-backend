import asyncio
import math
from datetime import datetime, timezone
from typing import Any

from app.indicators import calculate_indicators
from app.providers.binance_spot import BinanceSpotProvider

TIMEFRAMES = ("15m", "1h", "4h", "1d")


async def _timeframe_result(provider: BinanceSpotProvider, symbol: str, interval: str) -> dict[str, Any]:
    try:
        rows = await provider.klines(symbol, interval, 250)
        if not isinstance(rows, list) or len(rows) < 50:
            return {
                "status": "INCOMPLETE",
                "interval": interval,
                "candle_count": len(rows) if isinstance(rows, list) else 0,
                "error": "INSUFFICIENT_KLINE_DATA",
            }
        try:
            closes = [float(row[4]) for row in rows]
            volumes = [float(row[5]) for row in rows]
        except (TypeError, ValueError, IndexError, OverflowError):
            return {"status": "INCOMPLETE", "interval": interval,
                    "error": "MALFORMED_KLINE_DATA"}
        if any(not math.isfinite(value) or value <= 0 for value in closes):
            return {"status": "INCOMPLETE", "interval": interval,
                    "error": "INVALID_CLOSE_PRICE"}
        if any(not math.isfinite(value) or value < 0 for value in volumes):
            return {"status": "INCOMPLETE", "interval": interval,
                    "error": "INVALID_KLINE_VOLUME"}
        indicators = calculate_indicators(closes)
        ema20 = indicators["ema_20"]
        ema50 = indicators["ema_50"]
        trend = "UNKNOWN"
        if ema20 is not None and ema50 is not None:
            if closes[-1] > ema20 > ema50:
                trend = "BULLISH_STRUCTURE"
            elif closes[-1] < ema20 < ema50:
                trend = "BEARISH_STRUCTURE"
            else:
                trend = "MIXED_STRUCTURE"
        return {
            "status": "COMPLETED",
            "interval": interval,
            "candle_count": len(rows),
            "last_candle_open_time_ms": rows[-1][0] if rows else None,
            "last_candle_close_time_ms": rows[-1][6] if rows else None,
            "latest_volume": volumes[-1] if volumes else None,
            "trend_structure": trend,
            "indicators": indicators,
        }
    except Exception as exc:
        return {"status": "FAILED", "interval": interval,
                "error": "UPSTREAM_UNAVAILABLE",
                "error_type": type(exc).__name__}


async def analyze_multiple_timeframes(
    provider: BinanceSpotProvider,
    symbol: str,
    intervals: tuple[str, ...] = TIMEFRAMES,
) -> dict[str, Any]:
    symbol = symbol.upper()
    sections = await asyncio.gather(
        *[_timeframe_result(provider, symbol, interval) for interval in intervals]
    )
    results = {item["interval"]: item for item in sections}
    completed = [item for item in sections if item["status"] == "COMPLETED"]
    failed = [item["interval"] for item in sections if item["status"] != "COMPLETED"]
    structures = [item["trend_structure"] for item in completed]
    if len(completed) != len(sections):
        alignment = "INCOMPLETE"
    elif structures and all(value == "BULLISH_STRUCTURE" for value in structures):
        alignment = "FULLY_BULLISH_ALIGNMENT"
    elif structures and all(value == "BEARISH_STRUCTURE" for value in structures):
        alignment = "FULLY_BEARISH_ALIGNMENT"
    elif structures and all(value in ("BULLISH_STRUCTURE", "BEARISH_STRUCTURE") for value in structures):
        alignment = "MIXED_DIRECTIONAL_ALIGNMENT"
    else:
        alignment = "MIXED_OR_NEUTRAL"

    return {
        "status": "COMPLETED" if not failed else "INCOMPLETE",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "Binance Spot public REST API",
        "symbol": symbol,
        "requested_timeframes": list(intervals),
        "completed_timeframes": len(completed),
        "failed_timeframes": failed,
        "alignment": alignment,
        "timeframes": results,
        "warning": "Multi-timeframe alignment is descriptive, not a forecast or standalone trade signal.",
    }


async def analyze_btc_market_condition(provider: BinanceSpotProvider) -> dict[str, Any]:
    btc, eth = await asyncio.gather(
        analyze_multiple_timeframes(provider, "BTCUSDT"),
        analyze_multiple_timeframes(provider, "ETHUSDT"),
    )
    try:
        tickers = await provider.all_24h_tickers()
        by_symbol = {item.get("symbol"): item for item in tickers}
        btc_ticker = by_symbol.get("BTCUSDT")
        eth_ticker = by_symbol.get("ETHUSDT")
        if not btc_ticker or not eth_ticker:
            raise ValueError("BTCUSDT or ETHUSDT 24h ticker missing")
        market_24h = {
            "btc_price_change_percent": float(btc_ticker["priceChangePercent"]),
            "btc_quote_volume_usdt": float(btc_ticker["quoteVolume"]),
            "eth_price_change_percent": float(eth_ticker["priceChangePercent"]),
            "eth_quote_volume_usdt": float(eth_ticker["quoteVolume"]),
        }
        ticker_status = "COMPLETED"
    except Exception as exc:
        market_24h = {"error": "UPSTREAM_UNAVAILABLE",
                      "error_type": type(exc).__name__}
        ticker_status = "FAILED"

    daily = btc["timeframes"].get("1d", {})
    four_hour = btc["timeframes"].get("4h", {})
    daily_trend = daily.get("trend_structure", "UNKNOWN")
    four_hour_trend = four_hour.get("trend_structure", "UNKNOWN")
    if daily_trend == "BULLISH_STRUCTURE" and four_hour_trend == "BULLISH_STRUCTURE":
        regime = "BULLISH_TREND_CONTEXT"
    elif daily_trend == "BEARISH_STRUCTURE" and four_hour_trend == "BEARISH_STRUCTURE":
        regime = "BEARISH_TREND_CONTEXT"
    elif daily_trend == "UNKNOWN" or four_hour_trend == "UNKNOWN":
        regime = "UNKNOWN"
    else:
        regime = "MIXED_OR_TRANSITIONAL"

    status = (
        "COMPLETED"
        if btc["status"] == "COMPLETED"
        and eth["status"] == "COMPLETED"
        and ticker_status == "COMPLETED"
        else "INCOMPLETE"
    )
    return {
        "status": status,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "Binance Spot public REST API",
        "regime": regime,
        "btc_multi_timeframe": btc,
        "eth_multi_timeframe": eth,
        "market_24h": {"status": ticker_status, **market_24h},
        "not_included": [
            "BTC dominance",
            "total crypto market capitalization",
            "stablecoin market capitalization and flows",
            "macro-economic calendar",
            "cross-exchange breadth",
        ],
        "warning": "This is a limited Binance Spot context indicator, not a complete global crypto market regime model.",
    }
