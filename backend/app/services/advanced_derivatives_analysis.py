from __future__ import annotations

import json
import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any

from app.services.funding_rates import FundingRateStore
from app.services.historical_klines import HistoricalKlineStore
from app.services.liquidation_collector import LiquidationStore
from app.services.open_interest import OPEN_INTEREST_PERIODS, OpenInterestStore


def _pct(first: float, last: float) -> float | None:
    if not math.isfinite(first) or not math.isfinite(last) or first == 0:
        return None
    return (last - first) / abs(first) * 100.0


class DerivativesSignalStore:
    """Idempotent storage for reproducible, descriptive derivatives signal snapshots."""

    def __init__(self, database_path: str) -> None:
        self.database_path = database_path
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(database_path) as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS derivatives_signal_snapshots (
                    market TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    period TEXT NOT NULL,
                    end_time_ms INTEGER NOT NULL,
                    generated_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    PRIMARY KEY (market, symbol, period, end_time_ms)
                )
            """)
            connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_derivatives_signal_history
                ON derivatives_signal_snapshots(market, symbol, period, end_time_ms)
            """)

    def save(self, payload: dict[str, Any]) -> dict[str, Any]:
        if payload.get("status") != "COMPLETED":
            return {"status": "NOT_STORED", "reason": "Only completed analysis snapshots are stored."}
        symbol = str(payload.get("symbol", "")).upper().strip()
        period = str(payload.get("period", ""))
        end_time_ms = payload.get("window", {}).get("end_time_ms")
        if not symbol or period not in OPEN_INTEREST_PERIODS or not isinstance(end_time_ms, int):
            raise ValueError("Analysis snapshot requires symbol, supported period, and end timestamp")
        generated_at = datetime.now(timezone.utc).isoformat()
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
        with sqlite3.connect(self.database_path) as connection:
            connection.execute("""
                INSERT INTO derivatives_signal_snapshots
                    (market, symbol, period, end_time_ms, generated_at, payload_json)
                VALUES ('USD_M', ?, ?, ?, ?, ?)
                ON CONFLICT(market, symbol, period, end_time_ms) DO UPDATE SET
                    generated_at=excluded.generated_at,
                    payload_json=excluded.payload_json
            """, (symbol, period, end_time_ms, generated_at, encoded))
            total = connection.execute("""
                SELECT COUNT(*) FROM derivatives_signal_snapshots
                WHERE market='USD_M' AND symbol=? AND period=?
            """, (symbol, period)).fetchone()[0]
        return {
            "status": "STORED", "symbol": symbol, "period": period,
            "end_time_ms": end_time_ms, "total_snapshots": int(total),
            "generated_at": generated_at,
        }

    def history(
        self, symbol: str, period: str = "1h",
        start_time_ms: int | None = None, end_time_ms: int | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        symbol = symbol.upper().strip()
        if not symbol:
            raise ValueError("symbol must not be empty")
        if period not in OPEN_INTEREST_PERIODS:
            raise ValueError("Unsupported open-interest period")
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        if start_time_ms is not None and start_time_ms < 0:
            raise ValueError("start_time_ms must be non-negative")
        if end_time_ms is not None and end_time_ms < 0:
            raise ValueError("end_time_ms must be non-negative")
        if start_time_ms is not None and end_time_ms is not None and end_time_ms < start_time_ms:
            raise ValueError("end_time_ms must be >= start_time_ms")
        clauses = ["market='USD_M'", "symbol=?", "period=?"]
        params: list[Any] = [symbol, period]
        if start_time_ms is not None:
            clauses.append("end_time_ms>=?")
            params.append(start_time_ms)
        if end_time_ms is not None:
            clauses.append("end_time_ms<=?")
            params.append(end_time_ms)
        params.append(limit)
        with sqlite3.connect(self.database_path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                f"SELECT end_time_ms, generated_at, payload_json FROM derivatives_signal_snapshots "
                f"WHERE {' AND '.join(clauses)} ORDER BY end_time_ms DESC LIMIT ?", params
            ).fetchall()
        snapshots = [
            {"end_time_ms": row["end_time_ms"], "generated_at": row["generated_at"],
             "analysis": json.loads(row["payload_json"])}
            for row in reversed(rows)
        ]
        return {
            "status": "COMPLETED" if snapshots else "NO_STORED_DATA",
            "market": "USD_M", "symbol": symbol, "period": period,
            "returned_count": len(snapshots), "snapshots": snapshots,
            "source": "Locally stored derivatives analysis snapshots.",
        }


class AdvancedDerivativesAnalysis:
    """Trend, acceleration, divergence, funding-extreme and liquidation context."""

    def __init__(
        self, funding: FundingRateStore, open_interest: OpenInterestStore,
        klines: HistoricalKlineStore, liquidations: LiquidationStore,
        signal_store: DerivativesSignalStore,
    ) -> None:
        self.funding = funding
        self.open_interest = open_interest
        self.klines = klines
        self.liquidations = liquidations
        self.signal_store = signal_store

    def analyze(
        self, symbol: str, period: str = "1h", price_interval: str = "1h",
        limit: int = 48, funding_abs_threshold: float = 0.001,
        spike_mad_multiplier: float = 3.5,
    ) -> dict[str, Any]:
        symbol = symbol.strip().upper()
        if not symbol or len(symbol) > 40:
            raise ValueError("Invalid symbol")
        if period not in OPEN_INTEREST_PERIODS:
            raise ValueError("Unsupported open-interest period")
        if not price_interval or len(price_interval) > 5:
            raise ValueError("Invalid price interval")
        if not 6 <= limit <= 500:
            raise ValueError("limit must be between 6 and 500 for trend analysis")
        if not math.isfinite(funding_abs_threshold) or not 0 <= funding_abs_threshold <= 0.1:
            raise ValueError("funding_abs_threshold must be between 0 and 0.1")
        if not math.isfinite(spike_mad_multiplier) or not 1 <= spike_mad_multiplier <= 10:
            raise ValueError("spike_mad_multiplier must be between 1 and 10")

        oi = self.open_interest.history("USD_M", symbol, period, limit=limit)
        records = oi["records"]
        if len(records) < 6:
            return {
                "status": "INSUFFICIENT_DATA", "symbol": symbol, "period": period,
                "required_records": 6, "available_records": len(records),
                "analysis": None,
                "limitations": ["At least six stored open-interest records are required for baseline trend and spike checks."],
            }

        oi_changes = []
        for previous, current in zip(records, records[1:]):
            change = _pct(previous["sum_open_interest"], current["sum_open_interest"])
            oi_changes.append({
                "from_time_ms": previous["timestamp_ms"],
                "to_time_ms": current["timestamp_ms"],
                "change_percent": change,
            })
        valid_changes = [x["change_percent"] for x in oi_changes if x["change_percent"] is not None]
        latest_change = valid_changes[-1] if valid_changes else None
        previous_change = valid_changes[-2] if len(valid_changes) >= 2 else None
        acceleration = (
            latest_change - previous_change
            if latest_change is not None and previous_change is not None else None
        )

        baseline = valid_changes[:-1]
        spike = {
            "status": "INSUFFICIENT_BASELINE", "method": "MEDIAN_ABSOLUTE_DEVIATION",
            "baseline_count": len(baseline), "multiplier": spike_mad_multiplier,
            "modified_z_score": None, "baseline_median_percent": None,
            "baseline_mad_percent": None,
        }
        if len(baseline) >= 5 and latest_change is not None:
            center = median(baseline)
            mad = median([abs(value - center) for value in baseline])
            spike.update({"baseline_median_percent": center, "baseline_mad_percent": mad})
            if mad > 0:
                score = 0.6745 * (latest_change - center) / mad
                spike.update({
                    "status": "SPIKE_CANDIDATE" if abs(score) >= spike_mad_multiplier else "NO_SPIKE",
                    "modified_z_score": score,
                })
            else:
                spike["status"] = "BASELINE_VARIANCE_ZERO"

        start_ms, end_ms = records[0]["timestamp_ms"], records[-1]["timestamp_ms"]
        prices = self.klines.history(
            "USD_M", symbol, price_interval, start_time_ms=start_ms,
            end_time_ms=end_ms, limit=5000,
        )["candles"]
        price_change = (
            _pct(prices[-2]["close"], prices[-1]["close"]) if len(prices) >= 2 else None
        )
        latest_oi = latest_change
        divergence = (
            "PRICE_OI_DIVERGENCE_CANDIDATE"
            if price_change is not None and latest_oi is not None and price_change * latest_oi < 0
            else "NO_DIVERGENCE_DETECTED"
            if price_change is not None and latest_oi is not None
            else "INSUFFICIENT_PRICE_OR_OI_CHANGE_DATA"
        )

        funding = self.funding.history(
            "USD_M", symbol, start_time_ms=start_ms, end_time_ms=end_ms, limit=5000,
        )["events"]
        latest_funding = funding[-1]["funding_rate"] if funding else None
        funding_extreme = (
            abs(latest_funding) >= funding_abs_threshold
            if latest_funding is not None else None
        )

        liquidation_rows = self.liquidations.recent(symbol, limit=1000)
        window_liquidations = [
            row for row in liquidation_rows
            if start_ms <= row["event_time_ms"] <= end_ms
        ]
        side_summary = {"SELL": {"count": 0, "approx_notional": 0.0},
                        "BUY": {"count": 0, "approx_notional": 0.0},
                        "OTHER": {"count": 0, "approx_notional": 0.0}}
        for row in window_liquidations:
            side = row["side"] if row["side"] in {"SELL", "BUY"} else "OTHER"
            side_summary[side]["count"] += 1
            side_summary[side]["approx_notional"] += float(row["approx_cumulative_notional"] or 0)
        liquidation_context = {
            "status": "OBSERVED_EVENTS" if window_liquidations else "NO_MATCHING_STORED_EVENTS",
            "stored_events_in_window": len(window_liquidations),
            "by_force_order_side": side_summary,
            "coverage_warning": (
                "Binance force-order stream provides at most one liquidation snapshot per symbol per 1000ms; "
                "this local stream is not a complete liquidation tape."
            ),
        }

        if latest_change is None:
            trend = "UNAVAILABLE"
        elif latest_change > 0:
            trend = "OI_RISING"
        elif latest_change < 0:
            trend = "OI_FALLING"
        else:
            trend = "OI_FLAT"
        if acceleration is None:
            acceleration_state = "UNAVAILABLE"
        elif acceleration > 0:
            acceleration_state = "ACCELERATING_UP"
        elif acceleration < 0:
            acceleration_state = "DECELERATING_OR_ACCELERATING_DOWN"
        else:
            acceleration_state = "UNCHANGED"

        result = {
            "status": "COMPLETED", "market": "USD_M", "symbol": symbol,
            "period": period, "price_interval": price_interval,
            "window": {
                "start_time_ms": start_ms, "end_time_ms": end_ms,
                "open_interest_records": len(records), "oi_change_observations": len(oi_changes),
                "price_candles": len(prices), "funding_events": len(funding),
            },
            "trend": {
                "latest_oi_change_percent": latest_change,
                "previous_oi_change_percent": previous_change,
                "acceleration_percentage_points": acceleration,
                "direction": trend, "acceleration_state": acceleration_state,
                "observations": oi_changes,
            },
            "oi_spike": spike,
            "price_oi_divergence": {
                "latest_price_change_percent": price_change,
                "latest_oi_change_percent": latest_oi,
                "classification": divergence,
            },
            "funding_extreme": {
                "latest_funding_rate": latest_funding,
                "absolute_threshold": funding_abs_threshold,
                "is_extreme_by_configured_threshold": funding_extreme,
                "threshold_is_user_configured_not_empirically_calibrated": True,
            },
            "liquidation_context": liquidation_context,
            "interpretation_warnings": [
                "A price/OI divergence is a descriptive candidate, not a confirmed reversal.",
                "Open interest is aggregate matched contracts and does not identify which side initiated positions.",
                "Funding extreme uses the supplied numeric threshold; it is not a universal market threshold.",
                "Zero MAD means the baseline has no robust spread; spike status is withheld.",
                "Liquidation stream snapshots are incomplete and absence of stored events is not proof that no liquidations occurred.",
                "Long/short positioning is not inferred from OI, price, funding, or liquidation side counts alone.",
            ],
        }
        result["signal_storage"] = self.signal_store.save(result)
        return result
