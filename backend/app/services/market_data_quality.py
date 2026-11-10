from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.historical_coverage import HistoricalCoverageEngine

_INTERVAL_MS = {
    "1m": 60_000, "3m": 180_000, "5m": 300_000, "15m": 900_000,
    "30m": 1_800_000, "1h": 3_600_000, "2h": 7_200_000,
    "4h": 14_400_000, "6h": 21_600_000, "8h": 28_800_000,
    "12h": 43_200_000, "1d": 86_400_000,
}
_PERIOD_MS = {
    "5m": 300_000, "15m": 900_000, "30m": 1_800_000,
    "1h": 3_600_000, "2h": 7_200_000, "4h": 14_400_000,
    "6h": 21_600_000, "12h": 43_200_000, "1d": 86_400_000,
}


class MarketDataQualityEngine:
    """Audits local data presence and freshness without inventing stream completeness."""

    def __init__(
        self, kline_db: str, funding_db: str, open_interest_db: str,
        ratio_db: str, aggregate_trade_db: str, order_book_db: str,
    ) -> None:
        self.kline_db = kline_db
        self.funding_db = funding_db
        self.open_interest_db = open_interest_db
        self.ratio_db = ratio_db
        self.aggregate_trade_db = aggregate_trade_db
        self.order_book_db = order_book_db

    @staticmethod
    def _query(db_path: str, sql: str, params: tuple[Any, ...]) -> tuple[int, int | None]:
        if not Path(db_path).exists():
            return 0, None
        try:
            with sqlite3.connect(f"file:{Path(db_path).resolve()}?mode=ro", uri=True) as db:
                row = db.execute(sql, params).fetchone()
        except sqlite3.Error:
            return -1, None
        if not row:
            return 0, None
        return int(row[0] or 0), int(row[1]) if row[1] is not None else None

    @staticmethod
    def _freshness(timestamp_ms: int | None, now_ms: int, stale_after_ms: int) -> str:
        if timestamp_ms is None:
            return "NO_DATA"
        age = now_ms - timestamp_ms
        if age < 0:
            return "FUTURE_TIMESTAMP"
        return "STALE" if age > stale_after_ms else "FRESH"

    def inspect(
        self, market: str, symbol: str, interval: str = "1h",
        lookback_hours: int = 168, now_ms: int | None = None,
    ) -> dict[str, Any]:
        market, symbol = market.upper(), symbol.upper().strip()
        if market not in {"SPOT", "USD_M", "COIN_M"}:
            raise ValueError("market must be SPOT, USD_M, or COIN_M")
        if not symbol:
            raise ValueError("symbol must not be empty")
        if interval not in _INTERVAL_MS:
            raise ValueError("interval must be a fixed interval from 1m through 1d")
        if not 1 <= lookback_hours <= 2160:
            raise ValueError("lookback_hours must be between 1 and 2160")
        now = int(now_ms if now_ms is not None else datetime.now(timezone.utc).timestamp() * 1000)
        interval_ms = _INTERVAL_MS[interval]

        candle_count, latest_candle_open = self._query(
            self.kline_db,
            "SELECT COUNT(*), MAX(open_time_ms) FROM historical_klines WHERE market=? AND symbol=? AND interval=?",
            (market, symbol, interval),
        )
        latest_close = None
        if latest_candle_open is not None:
            _, latest_close = self._query(
                self.kline_db,
                "SELECT COUNT(*), MAX(close_time_ms) FROM historical_klines WHERE market=? AND symbol=? AND interval=? AND open_time_ms=?",
                (market, symbol, interval, latest_candle_open),
            )
        candle_freshness = "UNKNOWN" if candle_count < 0 else self._freshness(latest_close, now, interval_ms * 2)
        coverage = None
        if latest_candle_open is not None:
            first_open = max(0, latest_candle_open - lookback_hours * 3_600_000)
            first_open = (first_open // interval_ms) * interval_ms
            try:
                coverage = HistoricalCoverageEngine(self.kline_db).inspect(
                    market, symbol, interval, first_open, latest_candle_open
                )
            except ValueError as exc:
                coverage = {"status": "NOT_MEASURABLE", "reason": str(exc)}
        candle_status = (
            "UNKNOWN" if candle_count < 0 else
            "NO_DATA" if candle_count == 0 else
            "STALE" if candle_freshness in {"STALE", "FUTURE_TIMESTAMP"} else
            "DEGRADED" if coverage and coverage.get("status") == "INCOMPLETE" else
            "HEALTHY" if coverage and coverage.get("status") == "COMPLETE" else "UNKNOWN"
        )

        sources: dict[str, Any] = {
            "historical_klines": {
                "status": candle_status,
                "freshness": candle_freshness,
                "record_count": candle_count,
                "latest_open_time_ms": latest_candle_open,
                "latest_close_time_ms": latest_close,
                "age_ms": now - latest_close if latest_close is not None else None,
                "stale_after_ms": interval_ms * 2,
                "coverage": coverage,
                "duplicate_open_times": 0,
                "duplicate_note": "The SQLite primary key prevents duplicate (market, symbol, interval, open_time_ms) rows.",
            }
        }

        queries = [
            ("funding_rates", self.funding_db,
             "SELECT COUNT(*), MAX(funding_time_ms) FROM historical_funding_rates WHERE market='USD_M' AND symbol=?",
             (symbol,), 24 * 3_600_000, "Funding events are irregularly sampled; freshness is a 24-hour operational threshold, not an expected schedule."),
            ("open_interest", self.open_interest_db,
             "SELECT COUNT(*), MAX(timestamp_ms) FROM historical_open_interest WHERE market='USD_M' AND symbol=? AND period=?",
             (symbol, interval if interval in _PERIOD_MS else "1h"), max(3 * _PERIOD_MS.get(interval, 3_600_000), 3_600_000),
             "Freshness threshold is three selected periods; it does not establish continuous coverage."),
            ("derivatives_ratios", self.ratio_db,
             "SELECT COUNT(*), MAX(timestamp_ms) FROM derivatives_ratio_history WHERE market='USD_M' AND symbol=?",
             (symbol,), 3 * 3_600_000, "Ratio freshness uses a three-hour operational threshold; records from different ratio types are counted together and are not treated as synchronized."),
            ("aggregate_trades", self.aggregate_trade_db,
             "SELECT COUNT(*), MAX(trade_time_ms) FROM aggregate_trades WHERE market=? AND symbol=?",
             (market, symbol), 10 * 60_000, "Event gaps cannot be proven from stored rows alone; no exchange sequence/heartbeat completeness is retained."),
            ("order_book_samples", self.order_book_db,
             "SELECT COUNT(*), MAX(event_time_ms) FROM order_book_samples WHERE market=? AND symbol=?",
             (market, symbol), 10 * 60_000, "Sample freshness is measurable, but missing sample intervals and full depth-stream continuity are not reconstructed here."),
        ]
        for name, db_path, sql, params, stale_after, note in queries:
            count, latest = self._query(db_path, sql, params)
            freshness = "UNKNOWN" if count < 0 else self._freshness(latest, now, stale_after)
            sources[name] = {
                "status": "UNKNOWN" if count < 0 else "NO_DATA" if count == 0 else "NOT_MEASURABLE",
                "source_market": "USD_M" if name in {"funding_rates", "open_interest", "derivatives_ratios"} else market,
                "period": interval if name == "open_interest" else None,
                "freshness": freshness,
                "record_count": count,
                "latest_event_time_ms": latest,
                "age_ms": now - latest if latest is not None else None,
                "stale_after_ms": stale_after,
                "continuity": "NOT_MEASURABLE",
                "note": note,
            }

        return {
            "status": "COMPLETED",
            "market": market,
            "symbol": symbol,
            "interval": interval,
            "lookback_hours": lookback_hours,
            "generated_at": datetime.fromtimestamp(now / 1000, tz=timezone.utc).isoformat(),
            "sources": sources,
            "limitations": [
                "This report audits local SQLite data only; it does not fetch or verify live Binance data.",
                "Freshness thresholds are operational heuristics, not exchange guarantees.",
                "Aggregate-trade and order-book sample freshness does not prove gap-free stream capture.",
                "Funding and open-interest series are reported only when locally stored; absent records are not backfilled.",
            ],
        }
