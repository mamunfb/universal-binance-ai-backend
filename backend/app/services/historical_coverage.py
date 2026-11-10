from __future__ import annotations

import calendar
import sqlite3
from datetime import datetime, timezone
from typing import Any

_FIXED_INTERVAL_MS = {
    "1m": 60_000, "3m": 180_000, "5m": 300_000,
    "15m": 900_000, "30m": 1_800_000,
    "1h": 3_600_000, "2h": 7_200_000, "4h": 14_400_000,
    "6h": 21_600_000, "8h": 28_800_000, "12h": 43_200_000,
    "1d": 86_400_000, "3d": 259_200_000,
}


def _utc_ms(value: datetime) -> int:
    return int(value.replace(tzinfo=timezone.utc).timestamp() * 1000)


def _month_open_ms(year: int, month: int) -> int:
    return _utc_ms(datetime(year, month, 1))


def _next_open(open_ms: int, interval: str) -> int:
    if interval in _FIXED_INTERVAL_MS:
        return open_ms + _FIXED_INTERVAL_MS[interval]
    current = datetime.fromtimestamp(open_ms / 1000, tz=timezone.utc)
    if interval == "1w":
        return open_ms + 7 * 86_400_000
    if interval == "1M":
        year, month = current.year, current.month + 1
        if month == 13:
            year, month = year + 1, 1
        return _month_open_ms(year, month)
    raise ValueError("Unsupported interval")


def _is_aligned(open_ms: int, interval: str) -> bool:
    if interval == "1M":
        dt = datetime.fromtimestamp(open_ms / 1000, tz=timezone.utc)
        return dt.day == 1 and dt.hour == dt.minute == dt.second == dt.microsecond == 0
    if interval == "1w":
        dt = datetime.fromtimestamp(open_ms / 1000, tz=timezone.utc)
        return dt.weekday() == 0 and dt.hour == dt.minute == dt.second == dt.microsecond == 0
    duration = _FIXED_INTERVAL_MS.get(interval)
    return duration is not None and open_ms % duration == 0


class HistoricalCoverageEngine:
    """Compare stored candle opens with the expected UTC interval grid."""

    def __init__(self, database_path: str, max_expected_candles: int = 100_000) -> None:
        self.database_path = database_path
        self.max_expected_candles = max_expected_candles

    def inspect(
        self, market: str, symbol: str, interval: str,
        start_time_ms: int, end_time_ms: int,
    ) -> dict[str, Any]:
        market, symbol = market.upper(), symbol.upper()
        if market not in {"SPOT", "USD_M", "COIN_M"}:
            raise ValueError("market must be SPOT, USD_M, or COIN_M")
        if not symbol.strip():
            raise ValueError("symbol must not be empty")
        if start_time_ms < 0 or end_time_ms < start_time_ms:
            raise ValueError("Require 0 <= start_time_ms <= end_time_ms")
        if interval not in {*_FIXED_INTERVAL_MS, "1w", "1M"}:
            raise ValueError("Unsupported interval")
        if not _is_aligned(start_time_ms, interval) or not _is_aligned(end_time_ms, interval):
            raise ValueError("start_time_ms and end_time_ms must align to UTC candle open times")

        expected: list[int] = []
        cursor = start_time_ms
        while cursor <= end_time_ms:
            expected.append(cursor)
            if len(expected) > self.max_expected_candles:
                raise ValueError(f"Requested range exceeds {self.max_expected_candles} expected candles")
            cursor = _next_open(cursor, interval)

        with sqlite3.connect(self.database_path) as connection:
            rows = connection.execute(
                """SELECT open_time_ms FROM historical_klines
                   WHERE market=? AND symbol=? AND interval=?
                     AND open_time_ms>=? AND open_time_ms<=?
                   ORDER BY open_time_ms""",
                (market, symbol, interval, start_time_ms, end_time_ms),
            ).fetchall()
        stored = {int(row[0]) for row in rows}
        expected_set = set(expected)
        unexpected = sorted(stored - expected_set)
        missing = [stamp for stamp in expected if stamp not in stored]

        gaps: list[dict[str, int]] = []
        for stamp in missing:
            if gaps and _next_open(gaps[-1]["end_open_time_ms"], interval) == stamp:
                gaps[-1]["end_open_time_ms"] = stamp
                gaps[-1]["missing_count"] += 1
            else:
                gaps.append({
                    "start_open_time_ms": stamp,
                    "end_open_time_ms": stamp,
                    "missing_count": 1,
                })

        expected_count = len(expected)
        stored_expected_count = expected_count - len(missing)
        if not stored:
            status = "NO_STORED_DATA"
        elif missing:
            status = "INCOMPLETE"
        else:
            status = "COMPLETE"

        return {
            "status": status,
            "market": market,
            "symbol": symbol,
            "interval": interval,
            "requested_range": {
                "start_open_time_ms": start_time_ms,
                "end_open_time_ms": end_time_ms,
            },
            "coverage": {
                "expected_candle_count": expected_count,
                "stored_candle_count": stored_expected_count,
                "missing_candle_count": len(missing),
                "coverage_ratio": round(stored_expected_count / expected_count, 8) if expected_count else 1.0,
                "contiguous": not missing,
                "gaps": gaps,
                "unexpected_stored_open_times": unexpected,
            },
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": "Local SQLite historical candle store",
            "warning": "COMPLETE means every expected candle open exists in local storage for this requested range; it does not independently verify exchange authenticity, candle finality, or upstream completeness.",
        }
