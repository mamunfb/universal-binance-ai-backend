from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo


BST = ZoneInfo("Asia/Dhaka")
SIGNAL_LIFE_HOURS = {
    "5m": 4, "15m": 4, "1h": 24, "4h": 72, "1d": 72,
}


def _parse_aware(value: str, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be an ISO-8601 timestamp with timezone")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be a valid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include a timezone offset")
    return parsed.astimezone(timezone.utc)


def build_signal_lifecycle(
    *,
    symbol: str,
    market: str,
    direction: str,
    driver_timeframe: str,
    analysis_timestamp: str,
    entry_window_start: str | None = None,
    entry_window_end: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Validate user/model-supplied signal timing; never forecast an entry window."""
    normalized_symbol = symbol.strip().upper()
    normalized_market = market.strip().upper()
    normalized_direction = direction.strip().upper()
    if not normalized_symbol or len(normalized_symbol) > 30:
        raise ValueError("symbol must contain 1 to 30 characters")
    if normalized_market not in {"SPOT", "USD_M", "COIN_M"}:
        raise ValueError("market must be SPOT, USD_M, or COIN_M")
    allowed = {"LONG"} if normalized_market == "SPOT" else {"LONG", "SHORT"}
    if normalized_direction not in allowed:
        raise ValueError("SPOT supports LONG only; Futures supports LONG or SHORT")
    timeframe = driver_timeframe.strip().lower()
    if timeframe not in SIGNAL_LIFE_HOURS:
        raise ValueError("driver_timeframe must be one of 5m, 15m, 1h, 4h, 1d")

    analyzed = _parse_aware(analysis_timestamp, "analysis_timestamp")
    life_hours = SIGNAL_LIFE_HOURS[timeframe]
    expires = analyzed + timedelta(hours=life_hours)
    bst_analysis = analyzed.astimezone(BST)
    signal_id = (
        f"{normalized_symbol}-{normalized_market}-{normalized_direction}-"
        f"{bst_analysis.strftime('%Y%m%d-%H%M')}"
    )
    start = _parse_aware(entry_window_start, "entry_window_start") if entry_window_start else None
    end = _parse_aware(entry_window_end, "entry_window_end") if entry_window_end else None
    if (start is None) != (end is None):
        raise ValueError("entry_window_start and entry_window_end must be supplied together")
    if start is not None and end is not None:
        if start < analyzed:
            raise ValueError("entry window cannot start before analysis_timestamp")
        if end < start:
            raise ValueError("entry_window_end must be at or after entry_window_start")
        if end > expires:
            raise ValueError("entry window must not exceed the maximum signal life")

    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if end is None:
        status = "TIMING_NOT_ESTABLISHED"
    elif current > end:
        status = "EXPIRED"
    else:
        status = "WAIT"

    return {
        "status": status,
        "signal_id": signal_id,
        "market": normalized_market,
        "symbol": normalized_symbol,
        "direction": normalized_direction,
        "driver_timeframe": timeframe,
        "maximum_signal_life_hours": life_hours,
        "analysis_timestamp_bst": bst_analysis.isoformat(),
        "signal_expiration_bst": expires.astimezone(BST).isoformat(),
        "entry_window_start_bst": start.astimezone(BST).isoformat() if start else None,
        "entry_window_end_bst": end.astimezone(BST).isoformat() if end else None,
        "entry_window_status": status,
        "decision_cap": "WAIT" if status in {"TIMING_NOT_ESTABLISHED", "WAIT"} else "NO_TRADE",
        "timing_is_forecast": False,
        "limitations": [
            "This utility validates supplied timestamps and applies maximum signal-life rules; it does not predict an entry date, time, or price.",
            "A WAIT status does not confirm price, volume, news, technical, liquidity, or risk conditions.",
            "Expired signals must be revalidated with fresh market data before any new plan is created.",
        ],
    }
