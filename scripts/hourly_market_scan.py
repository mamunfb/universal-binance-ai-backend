from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Allow direct execution from the repository root or from GitHub Actions.
BACKEND_PATH = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_PATH))

from app.config import settings
from app.providers.binance_futures import BinanceFuturesProvider
from app.providers.binance_spot import BinanceSpotProvider
from app.services.futures_scanner import scan_futures_markets
from app.services.market_scanner import scan_spot_markets


MARKETS = ("SPOT", "USD_M", "COIN_M")


def summarize_status(results: dict[str, dict[str, Any]]) -> str:
    statuses = [
        (
            str(result.get("status", "UNKNOWN")).upper(),
            str(result.get("phase_status", result.get("status", "UNKNOWN"))).upper(),
        )
        for result in results.values()
    ]
    if any(status == "FAILED" for status, _ in statuses):
        return "FAILED"
    if any(status != "COMPLETED" or phase != "COMPLETED" for status, phase in statuses):
        return "INCOMPLETE"
    return "COMPLETED"


async def collect_market_scans() -> dict[str, dict[str, Any]]:
    """Scan every eligible symbol in Spot, USD-M and COIN-M without fixed symbol caps."""
    spot = BinanceSpotProvider(
        settings.binance_spot_base_url,
        timeout_seconds=settings.http_timeout_seconds,
    )
    results: dict[str, dict[str, Any]] = {}

    # Run sequentially to keep upstream request bursts modest and isolate failures.
    try:
        results["SPOT"] = await scan_spot_markets(spot)
    except Exception as exc:
        results["SPOT"] = {
            "status": "FAILED",
            "market": "SPOT",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "error_code": "COLLECTOR_EXCEPTION",
            "error_type": type(exc).__name__,
        }

    for market in ("USD_M", "COIN_M"):
        try:
            provider = BinanceFuturesProvider(
                market,
                timeout_seconds=settings.http_timeout_seconds,
            )
            results[market] = await scan_futures_markets(provider)
        except Exception as exc:
            results[market] = {
                "status": "FAILED",
                "market": market,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "error_code": "COLLECTOR_EXCEPTION",
                "error_type": type(exc).__name__,
            }
    return results


def persist_scan_run(
    results: dict[str, dict[str, Any]],
    started_at: datetime,
) -> str:
    """Persist one complete hourly scan envelope in Neon/PostgreSQL."""
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is missing. Create a Neon PostgreSQL database and add "
            "its connection string as the GitHub Actions secret DATABASE_URL."
        )

    try:
        retention_days = int(os.environ.get("MARKET_SCAN_RETENTION_DAYS", "14"))
    except ValueError as exc:
        raise RuntimeError("MARKET_SCAN_RETENTION_DAYS must be an integer") from exc
    if not 1 <= retention_days <= 365:
        raise RuntimeError("MARKET_SCAN_RETENTION_DAYS must be between 1 and 365")

    # Import only at persistence time so scanner logic remains independently testable.
    import psycopg
    from psycopg.types.json import Jsonb

    run_id = str(uuid.uuid4())
    completed_at = datetime.now(timezone.utc)
    overall_status = summarize_status(results)
    payload = {
        "run_id": run_id,
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "overall_status": overall_status,
        "market_scope": list(MARKETS),
        "markets": results,
    }

    with psycopg.connect(database_url, sslmode="require", connect_timeout=15) as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS market_scan_runs (
                    run_id UUID PRIMARY KEY,
                    started_at TIMESTAMPTZ NOT NULL,
                    completed_at TIMESTAMPTZ NOT NULL,
                    overall_status TEXT NOT NULL,
                    market_count SMALLINT NOT NULL,
                    payload JSONB NOT NULL,
                    inserted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_market_scan_runs_completed_at
                ON market_scan_runs (completed_at DESC)
            """)
            cursor.execute("""
                INSERT INTO market_scan_runs (
                    run_id, started_at, completed_at, overall_status,
                    market_count, payload
                ) VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                run_id,
                started_at,
                completed_at,
                overall_status,
                len(results),
                Jsonb(payload),
            ))
            cursor.execute(
                "DELETE FROM market_scan_runs WHERE completed_at < "
                "NOW() - make_interval(days => %s)",
                (retention_days,),
            )
    return run_id


async def main() -> int:
    started_at = datetime.now(timezone.utc)
    results = await collect_market_scans()
    run_id = persist_scan_run(results, started_at)
    summary = {
        "run_id": run_id,
        "overall_status": summarize_status(results),
        "markets": {
            market: {
                "status": result.get("status"),
                "eligible_symbols": result.get("eligible_symbols"),
                "scanned_symbols": result.get("scanned_symbols"),
                "matched_symbols": result.get("matched_symbols"),
                "failed_symbols": result.get("failed_symbols"),
            }
            for market, result in results.items()
        },
    }
    print(json.dumps(summary, ensure_ascii=False, allow_nan=False))
    return 0 if summary["overall_status"] == "COMPLETED" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
