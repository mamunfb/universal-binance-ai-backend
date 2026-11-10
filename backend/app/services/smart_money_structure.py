from __future__ import annotations

import math
from typing import Any

from app.services.historical_klines import HistoricalKlineStore


class SmartMoneyMarketStructure:
    """Deterministic OHLC-derived structure candidates; not exchange order-flow data."""

    def __init__(self, history: HistoricalKlineStore) -> None:
        self.history = history

    @staticmethod
    def _validate_candle(row: dict[str, Any]) -> None:
        values = [float(row[key]) for key in ("open", "high", "low", "close")]
        if not all(math.isfinite(value) and value > 0 for value in values):
            raise ValueError("Stored candle prices must be finite and positive")
        open_, high, low, close = values
        if high < max(open_, close, low) or low > min(open_, close, high):
            raise ValueError("Stored candle has inconsistent OHLC values")

    @staticmethod
    def _pivots(candles: list[dict[str, Any]], left: int, right: int) -> tuple[list[dict], list[dict]]:
        highs: list[dict] = []
        lows: list[dict] = []
        for i in range(left, len(candles) - right):
            high = float(candles[i]["high"])
            low = float(candles[i]["low"])
            neighbours = candles[i-left:i] + candles[i+1:i+right+1]
            # Strict comparison prevents a flat plateau from creating many duplicate pivots.
            if all(high > float(item["high"]) for item in neighbours):
                highs.append({"index": i, "time_ms": candles[i]["open_time_ms"], "price": high})
            if all(low < float(item["low"]) for item in neighbours):
                lows.append({"index": i, "time_ms": candles[i]["open_time_ms"], "price": low})
        return highs, lows

    def analyze(
        self, market: str, symbol: str, interval: str = "1h",
        limit: int = 300, swing_left: int = 3, swing_right: int = 3,
    ) -> dict[str, Any]:
        market = market.upper().strip()
        symbol = symbol.upper().strip()
        if market not in {"SPOT", "USD_M", "COIN_M"}:
            raise ValueError("market must be SPOT, USD_M, or COIN_M")
        if not symbol or len(symbol) > 40:
            raise ValueError("Invalid symbol")
        allowed_intervals = {
            "1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h",
            "6h", "8h", "12h", "1d", "3d", "1w", "1M",
        }
        if interval not in allowed_intervals:
            raise ValueError("Unsupported candle interval")
        if not 30 <= limit <= 1000:
            raise ValueError("limit must be between 30 and 1000")
        if not 1 <= swing_left <= 10 or not 1 <= swing_right <= 10:
            raise ValueError("swing_left and swing_right must be between 1 and 10")

        candles = self.history.history(market, symbol, interval, limit=limit)["candles"]
        if len(candles) < max(30, swing_left + swing_right + 10):
            return {
                "status": "INSUFFICIENT_DATA", "market": market, "symbol": symbol,
                "interval": interval, "available_candles": len(candles),
                "required_candles": max(30, swing_left + swing_right + 10),
                "structure": "UNKNOWN", "limitations": ["Insufficient locally stored candles."],
            }
        for candle in candles:
            self._validate_candle(candle)

        highs, lows = self._pivots(candles, swing_left, swing_right)
        if len(highs) < 2 or len(lows) < 2:
            return {
                "status": "INSUFFICIENT_SWINGS", "market": market, "symbol": symbol,
                "interval": interval, "confirmed_swing_highs": len(highs),
                "confirmed_swing_lows": len(lows), "structure": "UNKNOWN",
                "limitations": ["At least two confirmed swing highs and lows are needed."],
            }

        last = candles[-1]
        close = float(last["close"])
        previous_highs = [pivot for pivot in highs if pivot["index"] < len(candles) - 1]
        previous_lows = [pivot for pivot in lows if pivot["index"] < len(candles) - 1]
        latest_high = previous_highs[-1]
        latest_low = previous_lows[-1]

        # Detect a close-through of the most recent confirmed opposing swing.
        crossed_up = close > latest_high["price"] and float(candles[-2]["close"]) <= latest_high["price"]
        crossed_down = close < latest_low["price"] and float(candles[-2]["close"]) >= latest_low["price"]
        prior_bias = "UNKNOWN"
        if len(highs) >= 2 and len(lows) >= 2:
            hh = highs[-1]["price"] > highs[-2]["price"]
            hl = lows[-1]["price"] > lows[-2]["price"]
            lh = highs[-1]["price"] < highs[-2]["price"]
            ll = lows[-1]["price"] < lows[-2]["price"]
            if hh and hl:
                prior_bias = "BULLISH"
            elif lh and ll:
                prior_bias = "BEARISH"

        if crossed_up:
            break_type = "CHoCH" if prior_bias == "BEARISH" else "BOS"
            break_direction = "BULLISH"
            broken_level = latest_high
        elif crossed_down:
            break_type = "CHoCH" if prior_bias == "BULLISH" else "BOS"
            break_direction = "BEARISH"
            broken_level = latest_low
        else:
            break_type = "NO_CONFIRMED_BREAK"
            break_direction = "NONE"
            broken_level = None

        sweeps = []
        recent_start = max(0, len(candles) - 20)
        for pivot in highs:
            if pivot["index"] < recent_start or pivot["index"] >= len(candles) - 1:
                continue
            for j in range(pivot["index"] + 1, len(candles)):
                row = candles[j]
                if float(row["high"]) > pivot["price"] and float(row["close"]) < pivot["price"]:
                    sweeps.append({
                        "type": "BUY_SIDE_LIQUIDITY_SWEEP_CANDIDATE",
                        "level": pivot["price"], "pivot_time_ms": pivot["time_ms"],
                        "sweep_time_ms": row["open_time_ms"],
                    })
                    break
        for pivot in lows:
            if pivot["index"] < recent_start or pivot["index"] >= len(candles) - 1:
                continue
            for j in range(pivot["index"] + 1, len(candles)):
                row = candles[j]
                if float(row["low"]) < pivot["price"] and float(row["close"]) > pivot["price"]:
                    sweeps.append({
                        "type": "SELL_SIDE_LIQUIDITY_SWEEP_CANDIDATE",
                        "level": pivot["price"], "pivot_time_ms": pivot["time_ms"],
                        "sweep_time_ms": row["open_time_ms"],
                    })
                    break
        sweeps.sort(key=lambda item: item["sweep_time_ms"], reverse=True)

        fvgs = []
        for i in range(2, len(candles)):
            first, middle, third = candles[i-2], candles[i-1], candles[i]
            if float(third["low"]) > float(first["high"]):
                lower, upper = float(first["high"]), float(third["low"])
                later = candles[i+1:]
                entered = any(float(row["low"]) <= upper for row in later)
                filled = any(float(row["low"]) <= lower for row in later)
                fvgs.append({
                    "type": "BULLISH_FVG_CANDIDATE",
                    "lower": lower, "upper": upper,
                    "formed_time_ms": third["open_time_ms"], "middle_candle_time_ms": middle["open_time_ms"],
                    "status": "FULLY_FILLED" if filled else "PARTIALLY_MITIGATED" if entered else "UNMITIGATED",
                })
            if float(third["high"]) < float(first["low"]):
                lower, upper = float(third["high"]), float(first["low"])
                later = candles[i+1:]
                entered = any(float(row["high"]) >= lower for row in later)
                filled = any(float(row["high"]) >= upper for row in later)
                fvgs.append({
                    "type": "BEARISH_FVG_CANDIDATE",
                    "lower": lower, "upper": upper,
                    "formed_time_ms": third["open_time_ms"], "middle_candle_time_ms": middle["open_time_ms"],
                    "status": "FULLY_FILLED" if filled else "PARTIALLY_MITIGATED" if entered else "UNMITIGATED",
                })

        order_block = None
        if broken_level is not None:
            for i in range(len(candles) - 2, max(-1, len(candles) - 21), -1):
                row = candles[i]
                open_, close_ = float(row["open"]), float(row["close"])
                if break_direction == "BULLISH" and close_ < open_:
                    order_block = {
                        "type": "BULLISH_ORDER_BLOCK_CANDIDATE",
                        "low": float(row["low"]), "high": float(row["high"]),
                        "candle_time_ms": row["open_time_ms"],
                        "definition": "Last bearish candle in the 20-candle lookback before the latest confirmed bullish close-through.",
                    }
                    break
                if break_direction == "BEARISH" and close_ > open_:
                    order_block = {
                        "type": "BEARISH_ORDER_BLOCK_CANDIDATE",
                        "low": float(row["low"]), "high": float(row["high"]),
                        "candle_time_ms": row["open_time_ms"],
                        "definition": "Last bullish candle in the 20-candle lookback before the latest confirmed bearish close-through.",
                    }
                    break

        range_high = max(float(row["high"]) for row in candles)
        range_low = min(float(row["low"]) for row in candles)
        midpoint = (range_high + range_low) / 2.0
        return {
            "status": "COMPLETED", "market": market, "symbol": symbol,
            "interval": interval, "structure": prior_bias,
            "current_close": close,
            "swing_points": {
                "confirmed_high_count": len(highs), "confirmed_low_count": len(lows),
                "latest_high": latest_high, "latest_low": latest_low,
                "pivot_confirmation": f"{swing_left} candles left and {swing_right} candles right; pivots are only known after right-side candles close.",
            },
            "structure_break": {
                "type": break_type, "direction": break_direction,
                "broken_level": broken_level,
                "confirmed_by_close": crossed_up or crossed_down,
            },
            "liquidity_sweep_candidates": sweeps[:20],
            "fair_value_gap_candidates": fvgs[-20:],
            "order_block_candidate": order_block,
            "premium_discount": {
                "range_high": range_high, "range_low": range_low,
                "equilibrium": midpoint,
                "zone": "PREMIUM" if close > midpoint else "DISCOUNT" if close < midpoint else "EQUILIBRIUM",
                "definition": "Position relative to the high/low of the entire requested candle sample; not an institutional dealing range.",
            },
            "coverage": {
                "candles_used": len(candles),
                "first_open_time_ms": candles[0]["open_time_ms"],
                "last_open_time_ms": last["open_time_ms"],
                "source": "Local historical OHLCV store",
            },
            "limitations": [
                "BOS, CHoCH, liquidity sweeps, FVG and order blocks are OHLC-based heuristic candidates, not verified institutional order flow.",
                "Swing pivots require right-side candles and are therefore confirmed with delay.",
                "No order book, tick trades, resting orders, participant identity or exchange liquidation intent is available in this calculation.",
                "Premium/discount uses the full requested sample high/low, not a validated dealing range.",
                "Missing candle intervals can distort structure; local coverage is not guaranteed contiguous.",
                "No prediction, probability, entry, stop, target or trading recommendation is produced.",
            ],
        }
