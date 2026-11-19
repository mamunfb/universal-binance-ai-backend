from __future__ import annotations

import math
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any

from app.services.liquidation_collector import LiquidationStore


class LiquidationClusterAnalysis:
    """Group observed force-order snapshots into transparent price buckets."""

    def __init__(self, store: LiquidationStore) -> None:
        self.store = store

    def analyze(
        self, symbol: str, start_time_ms: int | None = None,
        end_time_ms: int | None = None, limit: int = 5000,
        bucket_bps: int = 25, min_events: int = 1,
    ) -> dict[str, Any]:
        symbol = symbol.upper().strip()
        if not symbol or len(symbol) > 40:
            raise ValueError("Invalid symbol")
        for name, value in (("start_time_ms", start_time_ms), ("end_time_ms", end_time_ms)):
            if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
                raise ValueError(f"{name} must be a non-negative integer")
        if start_time_ms is not None and end_time_ms is not None and end_time_ms < start_time_ms:
            raise ValueError("end_time_ms must be >= start_time_ms")
        for name, value, maximum in (("limit", limit, 20000), ("bucket_bps", bucket_bps, 500), ("min_events", min_events, 1000)):
            if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
                raise ValueError(f"{name} must be an integer between 1 and {maximum}")

        clauses = ["symbol=?"]
        params: list[Any] = [symbol]
        if start_time_ms is not None:
            clauses.append("event_time_ms>=?")
            params.append(start_time_ms)
        if end_time_ms is not None:
            clauses.append("event_time_ms<=?")
            params.append(end_time_ms)
        params.append(limit)
        with sqlite3.connect(self.store.database_path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                "SELECT event_time_ms, trade_time_ms, symbol, side, status, "
                "average_price, cumulative_filled_quantity, approx_cumulative_notional "
                "FROM liquidation_events WHERE " + " AND ".join(clauses) +
                " ORDER BY event_time_ms DESC LIMIT ?", params,
            ).fetchall()
        events = [dict(row) for row in rows]
        if not events:
            return {
                "status": "NO_STORED_DATA", "symbol": symbol,
                "coverage": {"events_examined": 0, "events_usable": 0},
                "clusters": [], "limitations": [
                    "No locally stored liquidation snapshots match this symbol and time range."
                ],
            }

        buckets: dict[int, dict[str, Any]] = defaultdict(lambda: {
            "event_count": 0, "approx_notional": 0.0,
            "sell_side_notional": 0.0, "buy_side_notional": 0.0,
            "sell_side_events": 0, "buy_side_events": 0,
            "first_event_time_ms": None, "last_event_time_ms": None,
        })
        usable = 0
        invalid = 0
        width = bucket_bps / 10000.0
        for event in events:
            try:
                price = float(event["average_price"])
                quantity = float(event["cumulative_filled_quantity"])
                notional = float(event["approx_cumulative_notional"])
                timestamp = int(event["event_time_ms"])
                if not all(math.isfinite(v) for v in (price, quantity, notional)):
                    raise ValueError
                if price <= 0 or quantity < 0 or notional < 0 or timestamp < 0:
                    raise ValueError
                side = str(event["side"] or "").upper()
                if side not in {"BUY", "SELL"}:
                    raise ValueError
            except (TypeError, ValueError, KeyError, OverflowError):
                invalid += 1
                continue
            bucket_id = int(math.floor(math.log(price) / math.log1p(width)))
            bucket = buckets[bucket_id]
            bucket["event_count"] += 1
            bucket["approx_notional"] += notional
            side_key = "sell_side" if side == "SELL" else "buy_side"
            bucket[f"{side_key}_notional"] += notional
            bucket[f"{side_key}_events"] += 1
            bucket["first_event_time_ms"] = (
                timestamp if bucket["first_event_time_ms"] is None
                else min(bucket["first_event_time_ms"], timestamp)
            )
            bucket["last_event_time_ms"] = (
                timestamp if bucket["last_event_time_ms"] is None
                else max(bucket["last_event_time_ms"], timestamp)
            )
            usable += 1

        clusters = []
        for bucket_id, data in buckets.items():
            if data["event_count"] < min_events:
                continue
            lower = math.exp(bucket_id * math.log1p(width))
            upper = math.exp((bucket_id + 1) * math.log1p(width))
            clusters.append({
                "price_lower": lower,
                "price_upper": upper,
                "price_midpoint": (lower + upper) / 2,
                **data,
                "liquidation_side_context": {
                    "SELL": "LONG_POSITION_LIQUIDATION_SIDE_CANDIDATE",
                    "BUY": "SHORT_POSITION_LIQUIDATION_SIDE_CANDIDATE",
                },
            })
        clusters.sort(key=lambda item: item["approx_notional"], reverse=True)
        total_notional = sum(item["approx_notional"] for item in clusters)
        for cluster in clusters:
            cluster["share_of_clustered_notional_percent"] = (
                cluster["approx_notional"] / total_notional * 100
                if total_notional > 0 else None
            )

        return {
            "status": "COMPLETED" if clusters else "NO_CLUSTERS",
            "market": "USD_M",
            "symbol": symbol,
            "bucket_width_basis_points": bucket_bps,
            "coverage": {
                "events_examined": len(events),
                "events_usable": usable,
                "events_rejected": invalid,
                "clusters_returned": len(clusters),
                "truncated_at_limit": len(events) == limit,
                "first_event_time_ms": min(
                    (event["event_time_ms"] for event in events), default=None
                ),
                "last_event_time_ms": max(
                    (event["event_time_ms"] for event in events), default=None
                ),
            },
            "total_clustered_approx_notional": total_notional,
            "clusters": clusters,
            "methodology": {
                "bucket": "Logarithmic price buckets with width set by bucket_bps.",
                "notional": "Stored approximate cumulative filled quantity multiplied by average fill price.",
                "side_mapping": "Force-order SELL is labelled a long-position liquidation-side candidate; BUY is labelled a short-position liquidation-side candidate.",
            },
            "limitations": [
                "The Binance force-order stream is a partial snapshot feed, not a complete record of all liquidations.",
                "Clusters describe observed forced-order snapshots only; they are not predictions of future liquidation levels.",
                "Side mapping is an order-side interpretation and is labelled candidate, not verified account-position attribution.",
                "Approximate notional is based on reported cumulative filled quantity and average price; it is not independently reconciled.",
                "The collector must be enabled and running, and its SQLite history starts only after collection begins.",
                "When coverage.truncated_at_limit is true, older matching events were not examined.",
            ],
        }
