"""Private MCP stdio adapter for the personal crypto intelligence API.

Run one process per AI client and provide that client's key through environment
variables. The server never accepts API keys as tool arguments.
"""
from __future__ import annotations

import json
import os
from functools import wraps
import inspect
from typing import Any, get_args, get_type_hints
from urllib.parse import quote

import httpx
from mcp.server.fastmcp import FastMCP

CLIENT_NAMES = {"chatgpt", "gemini", "manus", "claude", "perplexity"}


def _load_credentials() -> tuple[str, str, str]:
    base_url = os.environ.get("PERSONAL_API_BASE_URL", "").rstrip("/")
    client_name = os.environ.get("MCP_CLIENT_NAME", "").lower()
    raw_keys = os.environ.get("AI_CLIENT_API_KEYS", "{}")
    try:
        keys = json.loads(raw_keys)
    except json.JSONDecodeError as exc:
        raise RuntimeError("AI_CLIENT_API_KEYS must contain valid JSON") from exc
    if not isinstance(keys, dict):
        raise RuntimeError("AI_CLIENT_API_KEYS must be a JSON object")
    if client_name not in CLIENT_NAMES:
        raise RuntimeError("MCP_CLIENT_NAME must be one of the five configured personal clients")
    api_key = keys.get(client_name)
    if not isinstance(api_key, str) or len(api_key) < 32:
        raise RuntimeError(f"A strong API key for {client_name} is not configured")
    if not base_url.startswith("https://") and not (
        base_url.startswith("http://") and os.environ.get("APP_ENV", "development") == "development"
    ):
        raise RuntimeError("PERSONAL_API_BASE_URL must use HTTPS outside local development")
    return base_url, client_name, api_key


BASE_URL, CLIENT_NAME, API_KEY = _load_credentials()
mcp = FastMCP(f"Personal Crypto Intelligence ({CLIENT_NAME})")


def _reject_boolean_integer_arguments(function):
    """Reject JSON booleans where MCP tool parameters require integers.

    Python treats bool as a subclass of int. MCP arguments are untrusted input,
    so validate the declared integer parameters before any range check or API call.
    """
    signature = inspect.signature(function)
    try:
        annotations = get_type_hints(function)
    except (NameError, TypeError):
        annotations = function.__annotations__
    integer_parameters = {
        name for name, annotation in annotations.items()
        if annotation is int or int in get_args(annotation)
    }

    @wraps(function)
    def validated(*args, **kwargs):
        bound = signature.bind(*args, **kwargs)
        for name in integer_parameters:
            value = bound.arguments.get(name)
            if isinstance(value, bool):
                raise ValueError(f"{name} must be an integer, not a boolean")
        return function(*args, **kwargs)

    return validated



def _post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Send an authenticated, fixed-path JSON request to the private API."""
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(f"{BASE_URL}{path}", json=payload,
                headers={"Authorization": f"Bearer {API_KEY}", "Accept": "application/json"})
    except httpx.RequestError:
        return {"status":"FAILED","error":{"code":"UPSTREAM_CONNECTION_ERROR","message":"The private API could not be reached."},"retryable":True}
    try:
        body=response.json()
    except ValueError:
        body=None
    if not response.is_success:
        return {"status":"FAILED","http_status":response.status_code,"response":body,"retryable":response.status_code in {429,502,503,504}}
    return body if isinstance(body,dict) else {"status":"FAILED","error":{"code":"UPSTREAM_INVALID_RESPONSE"}}


def _get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Call a fixed read-only API path and preserve structured evidence and errors."""
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(
                f"{BASE_URL}{path}",
                params=params,
                headers={"Authorization": f"Bearer {API_KEY}", "Accept": "application/json"},
            )
    except httpx.RequestError:
        return {
            "status": "FAILED",
            "error": {
                "code": "UPSTREAM_CONNECTION_ERROR",
                "message": "The private API could not be reached.",
            },
            "retryable": True,
        }

    request_id = response.headers.get("X-Request-ID")
    try:
        payload = response.json()
    except ValueError:
        payload = None

    if not response.is_success:
        body = payload if isinstance(payload, dict) else {}
        nested = body.get("detail") if isinstance(body.get("detail"), dict) else body
        error = nested.get("error") if isinstance(nested.get("error"), dict) else {}
        code = error.get("code") or {
            400: "BAD_REQUEST",
            401: "UNAUTHORIZED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            422: "VALIDATION_ERROR",
            429: "RATE_LIMITED",
            502: "UPSTREAM_ERROR",
            503: "SERVICE_UNAVAILABLE",
            504: "UPSTREAM_TIMEOUT",
        }.get(response.status_code, "HTTP_ERROR")
        result = {
            "status": "FAILED",
            "http_status": response.status_code,
            "error": {
                "code": code,
                "message": error.get("message") or "The private API request failed.",
            },
            "retryable": response.status_code in {429, 502, 503, 504},
        }
        details = error.get("details")
        if details is not None:
            result["error"]["details"] = details
        body_request_id = body.get("request_id")
        if request_id or body_request_id:
            result["request_id"] = request_id or body_request_id
        return result

    if not isinstance(payload, dict):
        result = {
            "status": "FAILED",
            "error": {
                "code": "UPSTREAM_INVALID_RESPONSE",
                "message": "The private API returned a non-object or invalid JSON response.",
            },
            "retryable": False,
        }
        if request_id:
            result["request_id"] = request_id
        return result

    # Return the canonical API payload unchanged to retain source, timestamps,
    # coverage, freshness, missing-data and warning fields.
    return payload


@mcp.tool()
@_reject_boolean_integer_arguments
def inspect_historical_kline_coverage(
    market: str, symbol: str, interval: str,
    start_time_ms: int, end_time_ms: int,
) -> dict:
    """Check whether every expected UTC candle open exists in local storage.

    A COMPLETE result means only that the local store contains every expected
    open time in the requested range; it is not an exchange completeness guarantee.
    """
    if market not in {"SPOT", "USD_M", "COIN_M"}:
        raise ValueError("market must be SPOT, USD_M, or COIN_M")
    if start_time_ms < 0 or end_time_ms < start_time_ms:
        raise ValueError("Require 0 <= start_time_ms <= end_time_ms")
    return _get(
        f"/api/v1/history/klines/{market}/{quote(symbol.upper(), safe='')}/coverage",
        {"interval": interval, "start_time_ms": start_time_ms, "end_time_ms": end_time_ms},
    )


@mcp.tool()
@_reject_boolean_integer_arguments
def get_spot_klines(symbol: str, interval: str = "1h", limit: int = 100) -> dict:
    """Get read-only Binance Spot OHLCV candles for a symbol and interval."""
    if not 1 <= limit <= 1000:
        raise ValueError("limit must be between 1 and 1000")
    return _get(f"/api/v1/markets/spot/klines/{quote(symbol.upper(), safe='')}", {"interval": interval, "limit": limit})


@mcp.tool()
@_reject_boolean_integer_arguments
def get_stored_historical_klines(market: str, symbol: str, interval: str = "1h", limit: int = 1000) -> dict:
    """Read locally stored historical OHLCV candles; does not collect or modify data."""
    if market not in {"SPOT", "USD_M", "COIN_M"}:
        raise ValueError("market must be SPOT, USD_M, or COIN_M")
    if not 1 <= limit <= 5000:
        raise ValueError("limit must be between 1 and 5000")
    return _get(
        f"/api/v1/history/klines/{market}/{quote(symbol.upper(), safe='')}",
        {"interval": interval, "limit": limit},
    )

@mcp.tool()
@_reject_boolean_integer_arguments
def get_spot_technical_analysis(symbol: str, interval: str = "1h", limit: int = 500) -> dict:
    """Get the backend's read-only Spot technical indicator analysis."""
    if not 1 <= limit <= 1000:
        raise ValueError("limit must be between 1 and 1000")
    return _get(f"/api/v1/analysis/spot/technical/{quote(symbol.upper(), safe='')}", {"interval": interval, "limit": limit})


@mcp.tool()
@_reject_boolean_integer_arguments
def get_market_evidence_snapshot(symbol: str) -> dict:
    """Get a research-only multi-source market evidence summary; no trade signal."""
    return _get(f"/api/v1/analysis/market-evidence/{quote(symbol.upper(), safe='')}")


@mcp.tool()
@_reject_boolean_integer_arguments
def get_spot_futures_basis(symbol: str) -> dict:
    """Compare latest Spot and USD-M Futures prices, basis, and funding rate."""
    return _get(f"/api/v1/analysis/spot-futures/basis/{quote(symbol.upper(), safe='')}")


@mcp.tool()
@_reject_boolean_integer_arguments
def get_futures_derivatives(symbol: str) -> dict:
    """Get read-only USD-M futures derivatives context for a symbol."""
    return _get(f"/api/v1/analysis/futures/usdm/derivatives/{quote(symbol.upper(), safe='')}")


@mcp.tool()
@_reject_boolean_integer_arguments
def get_news_intelligence(symbols: str = "BTC,ETH", hours: int = 72, limit: int = 100) -> dict:
    """Get source-aware crypto news intelligence; this is not a price forecast."""
    if not 1 <= hours <= 720 or not 1 <= limit <= 500:
        raise ValueError("hours must be 1..720 and limit must be 1..500")
    return _get("/api/v1/news/intelligence", {"symbols": symbols, "hours": hours, "limit": limit})


@mcp.tool()
@_reject_boolean_integer_arguments
def get_cross_chain_token_intelligence(
    asset_id: str,
    from_block: int,
    to_block: int,
    decimals: int = 18,
    limit: int = 50,
    window_blocks: int = 1000,
) -> dict:
    """Get indexed cross-chain token flows and verified cohort intelligence.

    Coverage, freshness, and incomplete_reasons must be preserved when interpreting
    the result. Net transfer flow does not prove buying, selling, or intent.
    """
    if from_block < 0 or to_block < from_block:
        raise ValueError("Require 0 <= from_block <= to_block")
    if not 0 <= decimals <= 36 or not 1 <= limit <= 100 or not 1 <= window_blocks <= 100000:
        raise ValueError("decimals, limit, or window_blocks is outside supported bounds")
    return _get(
        f"/api/v1/onchain/evm/cross-chain/token/{quote(asset_id, safe='')}/intelligence",
        {
            "from_block": from_block,
            "to_block": to_block,
            "decimals": decimals,
            "limit": limit,
            "window_blocks": window_blocks,
        },
    )


@mcp.tool()
@_reject_boolean_integer_arguments
def get_stored_funding_rate_history(
    symbol: str, start_time_ms: int | None = None,
    end_time_ms: int | None = None, limit: int = 1000,
) -> dict:
    """Read locally stored USD-M funding events and observed timestamp deltas."""
    if not 1 <= limit <= 5000:
        raise ValueError("limit must be between 1 and 5000")
    return _get(
        f"/api/v1/history/funding-rates/USD_M/{quote(symbol.upper(), safe='')}",
        {"start_time_ms": start_time_ms, "end_time_ms": end_time_ms, "limit": limit},
    )


@mcp.tool()
@_reject_boolean_integer_arguments
def analyze_combined_derivatives_intelligence(
    symbol: str, period: str = "1h", limit: int = 100,
) -> dict:
    """Analyze exact timestamp intersections of stored OI, account ratio, taker ratio and funding context."""
    if period not in {"5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d"}:
        raise ValueError("Unsupported derivatives period")
    if not 2 <= limit <= 500:
        raise ValueError("limit must be between 2 and 500")
    return _get(
        f"/api/v1/analysis/derivatives/combined/{quote(symbol.upper(), safe='')}",
        {"period": period, "limit": limit},
    )


@mcp.tool()
@_reject_boolean_integer_arguments
def get_stored_derivatives_ratio_history(
    symbol: str, ratio_type: str, period: str = "1h",
    start_time_ms: int | None = None, end_time_ms: int | None = None,
    limit: int = 200,
) -> dict:
    """Read locally stored USD-M global account or taker buy/sell ratio observations."""
    if ratio_type not in {"GLOBAL_LONG_SHORT", "TAKER_BUY_SELL"}:
        raise ValueError("ratio_type must be GLOBAL_LONG_SHORT or TAKER_BUY_SELL")
    if period not in {"5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d"}:
        raise ValueError("Unsupported ratio period")
    if not 1 <= limit <= 500:
        raise ValueError("limit must be between 1 and 500")
    return _get(
        f"/api/v1/history/derivatives-ratios/USD_M/{ratio_type}/{quote(symbol.upper(), safe='')}",
        {"period": period, "start_time_ms": start_time_ms,
         "end_time_ms": end_time_ms, "limit": limit},
    )


@mcp.tool()
@_reject_boolean_integer_arguments
def analyze_multi_timeframe_derivatives(
    symbol: str, periods: str = "5m,15m,1h,4h,1d", limit: int = 48,
) -> dict:
    """Compare locally stored derivatives evidence across explicitly selected timeframes."""
    allowed = {"5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d"}
    parsed = [part.strip() for part in periods.split(",")]
    if not 1 <= len(parsed) <= 9 or any(p not in allowed for p in parsed):
        raise ValueError("Unsupported timeframe list")
    if len(set(parsed)) != len(parsed):
        raise ValueError("Duplicate timeframes are not allowed")
    if not 6 <= limit <= 500:
        raise ValueError("limit must be between 6 and 500")
    return _get(
        f"/api/v1/analysis/derivatives/multi-timeframe/{quote(symbol.upper(), safe='')}",
        {"periods": ",".join(parsed), "limit": limit},
    )


@mcp.tool()
@_reject_boolean_integer_arguments
def analyze_advanced_derivatives(
    symbol: str, period: str = "1h", price_interval: str = "1h",
    limit: int = 48, funding_abs_threshold: float = 0.001,
    spike_mad_multiplier: float = 3.5,
) -> dict:
    """Analyze stored OI trend, acceleration, spikes, divergence, funding and liquidation context."""
    if period not in {"5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d"}:
        raise ValueError("Unsupported open-interest period")
    if not 6 <= limit <= 500:
        raise ValueError("limit must be between 6 and 500")
    if not 0 <= funding_abs_threshold <= 0.1:
        raise ValueError("funding_abs_threshold must be between 0 and 0.1")
    if not 1 <= spike_mad_multiplier <= 10:
        raise ValueError("spike_mad_multiplier must be between 1 and 10")
    return _get(
        f"/api/v1/analysis/derivatives/advanced/{quote(symbol.upper(), safe='')}",
        {"period": period, "price_interval": price_interval, "limit": limit,
         "funding_abs_threshold": funding_abs_threshold,
         "spike_mad_multiplier": spike_mad_multiplier},
    )


@mcp.tool()
@_reject_boolean_integer_arguments
def get_derivatives_signal_history(
    symbol: str, period: str = "1h", start_time_ms: int | None = None,
    end_time_ms: int | None = None, limit: int = 100,
) -> dict:
    """Read stored historical descriptive derivatives analysis snapshots."""
    if period not in {"5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d"}:
        raise ValueError("Unsupported open-interest period")
    if not 1 <= limit <= 1000:
        raise ValueError("limit must be between 1 and 1000")
    return _get(
        f"/api/v1/history/derivatives-signals/{quote(symbol.upper(), safe='')}",
        {"period": period, "start_time_ms": start_time_ms,
         "end_time_ms": end_time_ms, "limit": limit},
    )


@mcp.tool()
@_reject_boolean_integer_arguments
def analyze_funding_open_interest(
    symbol: str, period: str = "1h", price_interval: str = "1h", limit: int = 24,
) -> dict:
    """Analyze locally stored USD-M price, open-interest and funding history together."""
    if period not in {"5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d"}:
        raise ValueError("Unsupported open-interest period")
    if not 2 <= limit <= 500:
        raise ValueError("limit must be between 2 and 500")
    return _get(
        f"/api/v1/analysis/derivatives/funding-open-interest/{quote(symbol.upper(), safe='')}",
        {"period": period, "price_interval": price_interval, "limit": limit},
    )


@mcp.tool()
@_reject_boolean_integer_arguments
def get_stored_open_interest_history(
    symbol: str, period: str = "1h", start_time_ms: int | None = None,
    end_time_ms: int | None = None, limit: int = 500,
) -> dict:
    """Read locally stored USD-M open-interest statistics for one period."""
    if period not in {"5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d"}:
        raise ValueError("Unsupported open-interest period")
    if not 1 <= limit <= 5000:
        raise ValueError("limit must be between 1 and 5000")
    return _get(
        f"/api/v1/history/open-interest/USD_M/{quote(symbol.upper(), safe='')}",
        {"period": period, "start_time_ms": start_time_ms,
         "end_time_ms": end_time_ms, "limit": limit},
    )


@mcp.tool()
@_reject_boolean_integer_arguments
def inspect_market_data_quality(
    market: str, symbol: str, interval: str = "1h", lookback_hours: int = 168
) -> dict:
    """Audit local candle coverage and local market-data freshness; does not prove stream continuity."""
    if market not in {"SPOT", "USD_M", "COIN_M"}:
        raise ValueError("market must be SPOT, USD_M or COIN_M")
    if interval not in {"1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d"}:
        raise ValueError("Unsupported candle interval")
    if not 1 <= lookback_hours <= 2160:
        raise ValueError("lookback_hours must be between 1 and 2160")
    return _get(
        f"/api/v1/quality/market-data/{market}/{quote(symbol.upper(), safe='')}",
        {"interval": interval, "lookback_hours": lookback_hours},
    )


@mcp.tool()
@_reject_boolean_integer_arguments
def get_historical_collector_status() -> dict:
    """Check whether scheduled historical candle collection is enabled and healthy."""
    return _get("/api/v1/history/collector/status")


@mcp.tool()
@_reject_boolean_integer_arguments
def get_derivatives_collector_status() -> dict:
    """Check scheduled USD-M funding-rate and open-interest collection status."""
    return _get("/api/v1/history/derivatives-collector/status")


@mcp.tool()
@_reject_boolean_integer_arguments
def get_liquidation_collector_status() -> dict:
    """Check whether the optional liquidation snapshot collector is enabled."""
    return _get("/api/v1/analysis/futures/liquidations/status")


@mcp.tool()
@_reject_boolean_integer_arguments
def get_aggregate_trade_collector_status() -> dict:
    """Check optional Binance aggregate trade stream collector status."""
    return _get("/api/v1/history/aggregate-trades/status")


@mcp.tool()
@_reject_boolean_integer_arguments
def get_stored_aggregate_trades(
    market: str, symbol: str, limit: int = 1000,
    start_time_ms: int | None = None, end_time_ms: int | None = None,
) -> dict:
    """Read locally captured Binance aggregate trades and inferred taker side."""
    if market not in {"SPOT", "USD_M", "COIN_M"}:
        raise ValueError("market must be SPOT, USD_M or COIN_M")
    if not 1 <= limit <= 10000:
        raise ValueError("limit must be between 1 and 10000")
    if start_time_ms is not None and start_time_ms < 0:
        raise ValueError("start_time_ms must be non-negative")
    if end_time_ms is not None and end_time_ms < 0:
        raise ValueError("end_time_ms must be non-negative")
    if start_time_ms is not None and end_time_ms is not None and end_time_ms < start_time_ms:
        raise ValueError("end_time_ms must be >= start_time_ms")
    return _get(
        f"/api/v1/history/aggregate-trades/{market}/{quote(symbol.upper(), safe='')}",
        {"limit": limit, "start_time_ms": start_time_ms, "end_time_ms": end_time_ms},
    )


@mcp.tool()
@_reject_boolean_integer_arguments
def analyze_liquidity_behavior(
    market: str, symbol: str, min_removed_notional: float = 10000,
    min_aggressive_notional: float = 10000, max_absorption_move_bps: float = 2,
    trade_price_band_bps: float = 2,
) -> dict:
    """Analyze sampled liquidity changes, approximate trade flow and candidate absorption/pulling patterns."""
    if market not in {"SPOT", "USD_M", "COIN_M"}:
        raise ValueError("market must be SPOT, USD_M or COIN_M")
    return _get(
        f"/api/v1/analysis/liquidity-behavior/{market}/{quote(symbol.upper(), safe='')}",
        {
            "min_removed_notional": min_removed_notional,
            "min_aggressive_notional": min_aggressive_notional,
            "max_absorption_move_bps": max_absorption_move_bps,
            "trade_price_band_bps": trade_price_band_bps,
        },
    )


@mcp.tool()
@_reject_boolean_integer_arguments
def get_order_book_stream_status() -> dict:
    """Check optional sequence-aware order-book stream collector status."""
    return _get("/api/v1/history/order-book/status")


@mcp.tool()
@_reject_boolean_integer_arguments
def get_stored_order_book_history(
    market: str, symbol: str, limit: int = 100,
    start_time_ms: int | None = None, end_time_ms: int | None = None,
) -> dict:
    """Read locally captured synchronized order-book depth samples; no collection is triggered."""
    if market not in {"SPOT", "USD_M", "COIN_M"}:
        raise ValueError("market must be SPOT, USD_M or COIN_M")
    if not 1 <= limit <= 1000:
        raise ValueError("limit must be between 1 and 1000")
    if start_time_ms is not None and start_time_ms < 0:
        raise ValueError("start_time_ms must be non-negative")
    if end_time_ms is not None and end_time_ms < 0:
        raise ValueError("end_time_ms must be non-negative")
    if start_time_ms is not None and end_time_ms is not None and end_time_ms < start_time_ms:
        raise ValueError("end_time_ms must be >= start_time_ms")
    return _get(
        f"/api/v1/history/order-book/{market}/{quote(symbol.upper(), safe='')}",
        {"limit": limit, "start_time_ms": start_time_ms, "end_time_ms": end_time_ms},
    )


@mcp.tool()
@_reject_boolean_integer_arguments
def analyze_order_book_liquidity(
    market: str, symbol: str, limit: int = 100, wall_multiplier: float = 3.0,
) -> dict:
    """Read a Binance order-book snapshot and calculate visible liquidity metrics."""
    if market not in {"SPOT", "USD_M", "COIN_M"}:
        raise ValueError("Unsupported market")
    allowed = {1, 5, 10, 20, 50, 100, 500, 1000} if market == "SPOT" else {5, 10, 20, 50, 100, 500, 1000}
    if limit not in allowed:
        raise ValueError("Unsupported order book limit for market")
    if not 1 <= wall_multiplier <= 20:
        raise ValueError("wall_multiplier must be between 1 and 20")
    return _get(
        f"/api/v1/analysis/order-book/{market}/{quote(symbol.upper(), safe='')}",
        {"limit": limit, "wall_multiplier": wall_multiplier},
    )


@mcp.tool()
@_reject_boolean_integer_arguments
def analyze_smart_money_market_structure(
    market: str, symbol: str, interval: str = "1h", limit: int = 300,
    swing_left: int = 3, swing_right: int = 3,
) -> dict:
    """Analyze OHLC-derived BOS/CHoCH, liquidity sweep, FVG and order-block candidates."""
    if market not in {"SPOT", "USD_M", "COIN_M"}:
        raise ValueError("Unsupported market")
    if interval not in {
        "1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h",
        "6h", "8h", "12h", "1d", "3d", "1w", "1M",
    }:
        raise ValueError("Unsupported candle interval")
    if not 30 <= limit <= 1000:
        raise ValueError("limit must be between 30 and 1000")
    if not 1 <= swing_left <= 10 or not 1 <= swing_right <= 10:
        raise ValueError("swing_left and swing_right must be between 1 and 10")
    return _get(
        f"/api/v1/analysis/smart-money-structure/{market}/{quote(symbol.upper(), safe='')}",
        {"interval": interval, "limit": limit,
         "swing_left": swing_left, "swing_right": swing_right},
    )


@mcp.tool()
@_reject_boolean_integer_arguments
def analyze_historical_market_regime(
    market: str, symbol: str, interval: str = "1h", limit: int = 200,
) -> dict:
    """Classify locally stored candles into descriptive volatility and structure regimes."""
    if market not in {"SPOT", "USD_M", "COIN_M"}:
        raise ValueError("market must be SPOT, USD_M, or COIN_M")
    if not 40 <= limit <= 1000:
        raise ValueError("limit must be between 40 and 1000")
    if interval not in {
        "1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h",
        "6h", "8h", "12h", "1d", "3d", "1w", "1M",
    }:
        raise ValueError("Unsupported candle interval")
    return _get(
        f"/api/v1/analysis/market-regime/{market}/{quote(symbol.upper(), safe='')}",
        {"interval": interval, "limit": limit},
    )



@mcp.tool()
@_reject_boolean_integer_arguments
def evaluate_historical_signal_performance(
    symbol: str, period: str = "1h", price_interval: str = "1h",
    limit: int = 500, round_trip_cost_bps: float = 0.0,
) -> dict:
    """Evaluate forward price outcomes of stored descriptive snapshots; not a strategy backtest."""
    if period not in {"5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d"}:
        raise ValueError("Unsupported derivatives period")
    if not 1 <= limit <= 1000:
        raise ValueError("limit must be between 1 and 1000")
    if not 0 <= round_trip_cost_bps <= 500:
        raise ValueError("round_trip_cost_bps must be between 0 and 500")
    return _get(
        f"/api/v1/analysis/derivatives/signal-performance/{quote(symbol.upper(), safe='')}",
        {"period": period, "price_interval": price_interval,
         "limit": limit, "round_trip_cost_bps": round_trip_cost_bps},
    )


@mcp.tool()
@_reject_boolean_integer_arguments
def analyze_liquidation_clusters(
    symbol: str, start_time_ms: int | None = None,
    end_time_ms: int | None = None, limit: int = 5000,
    bucket_bps: int = 25, min_events: int = 1,
) -> dict:
    """Group locally stored USD-M force-order snapshots into observed price buckets."""
    if not 1 <= limit <= 20000:
        raise ValueError("limit must be between 1 and 20000")
    if not 1 <= bucket_bps <= 500:
        raise ValueError("bucket_bps must be between 1 and 500")
    if not 1 <= min_events <= 1000:
        raise ValueError("min_events must be between 1 and 1000")
    if start_time_ms is not None and start_time_ms < 0:
        raise ValueError("start_time_ms must be non-negative")
    if end_time_ms is not None and end_time_ms < 0:
        raise ValueError("end_time_ms must be non-negative")
    if start_time_ms is not None and end_time_ms is not None and end_time_ms < start_time_ms:
        raise ValueError("end_time_ms must be >= start_time_ms")
    return _get(
        f"/api/v1/analysis/futures/liquidation-clusters/{quote(symbol.upper(), safe='')}",
        {"start_time_ms": start_time_ms, "end_time_ms": end_time_ms,
         "limit": limit, "bucket_bps": bucket_bps, "min_events": min_events},
    )



@mcp.tool()
@_reject_boolean_integer_arguments
def analyze_order_flow_intelligence(
    market: str, symbol: str, lookback_minutes: int = 60,
    bin_size_bps: float = 5.0, value_area_pct: float = 70.0,
) -> dict:
    """Analyze locally stored aggregate trades for volume profile, CVD and divergence candidates."""
    if market not in {"SPOT", "USD_M", "COIN_M"}:
        raise ValueError("market must be SPOT, USD_M or COIN_M")
    if not 1 <= lookback_minutes <= 1440:
        raise ValueError("lookback_minutes must be between 1 and 1440")
    if not 0.1 <= bin_size_bps <= 500:
        raise ValueError("bin_size_bps must be between 0.1 and 500")
    if not 50 <= value_area_pct <= 99:
        raise ValueError("value_area_pct must be between 50 and 99")
    return _get(
        f"/api/v1/analysis/order-flow/{market}/{quote(symbol.upper(), safe='')}",
        {"lookback_minutes": lookback_minutes, "bin_size_bps": bin_size_bps,
         "value_area_pct": value_area_pct},
    )





@mcp.tool()
@_reject_boolean_integer_arguments
def get_market_confluence_history(market: str, symbol: str, interval: str = "1h", limit: int = 100) -> dict:
    """Read locally saved Market Structure + Order Flow confluence snapshots."""
    if market not in {"SPOT","USD_M","COIN_M"} or not 1 <= limit <= 1000: raise ValueError("Invalid market or limit")
    return _get(f"/api/v1/history/market-confluence/{market}/{quote(symbol.upper(),safe='')}",{"interval":interval,"limit":limit})


@mcp.tool()
@_reject_boolean_integer_arguments
def save_market_confluence_snapshot(
    market: str, symbol: str, interval: str, analyzed_at_ms: int,
    bias: str, alignment: str, reference_price: float | None = None,
    reference_close_time_ms: int | None = None, evidence_json: str = "{}",
) -> dict:
    """Persist one descriptive snapshot for later outcome evaluation; no trade is placed."""
    if market not in {"SPOT","USD_M","COIN_M"} or bias not in {"BULLISH","BEARISH","MIXED","UNKNOWN"}: raise ValueError("Invalid market or bias")
    try: evidence=json.loads(evidence_json)
    except json.JSONDecodeError as exc: raise ValueError("evidence_json must be valid JSON") from exc
    payload={"market":market,"symbol":symbol.upper(),"interval":interval,"analyzed_at_ms":analyzed_at_ms,
        "confluence":{"bias":bias,"alignment":alignment},
        "reference":{"price":reference_price,"close_time_ms":reference_close_time_ms},"evidence":evidence}
    return _post("/api/v1/history/market-confluence/snapshots",payload)


@mcp.tool()
@_reject_boolean_integer_arguments
def evaluate_market_confluence_performance(
    market: str, symbol: str, interval: str = "1h", price_interval: str = "1h", limit: int = 200,
) -> dict:
    """Evaluate descriptive forward outcomes for saved confluence snapshots."""
    if market not in {"SPOT","USD_M","COIN_M"} or not 1 <= limit <= 1000: raise ValueError("Invalid market or limit")
    return _get(f"/api/v1/analysis/market-confluence-performance/{market}/{quote(symbol.upper(),safe='')}",
        {"interval":interval,"price_interval":price_interval,"limit":limit})


@mcp.tool()
@_reject_boolean_integer_arguments
def analyze_market_structure_confluence(
    market: str, symbol: str, interval: str = "1h", limit: int = 300,
    periods: str = "15m,1h,4h,1d",
    bin_size_bps: float = 5.0, value_area_pct: float = 70.0,
) -> dict:
    """Summarize local market structure, regime, CVD, multi-timeframe flow and sweep evidence."""
    if market not in {"SPOT", "USD_M", "COIN_M"}:
        raise ValueError("market must be SPOT, USD_M or COIN_M")
    if interval not in {"1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d"}:
        raise ValueError("Unsupported candle interval")
    if not 40 <= limit <= 1000:
        raise ValueError("limit must be between 40 and 1000")
    selected = [item.strip() for item in periods.split(",") if item.strip()]
    allowed = {"5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d"}
    if not selected or len(selected) > 9 or len(set(selected)) != len(selected):
        raise ValueError("Select 1 to 9 unique timeframes")
    if any(item not in allowed for item in selected):
        raise ValueError("Unsupported order-flow timeframe")
    if not 0.1 <= bin_size_bps <= 500:
        raise ValueError("bin_size_bps must be between 0.1 and 500")
    if not 50 <= value_area_pct <= 99:
        raise ValueError("value_area_pct must be between 50 and 99")
    return _get(
        f"/api/v1/analysis/market-structure-confluence/{market}/{quote(symbol.upper(), safe='')}",
        {"interval": interval, "limit": limit, "periods": ",".join(selected),
         "bin_size_bps": bin_size_bps, "value_area_pct": value_area_pct},
    )


@mcp.tool()
@_reject_boolean_integer_arguments
def analyze_liquidity_sweep_confirmation(
    market: str, symbol: str, interval: str = "5m", limit: int = 300,
    equal_level_tolerance_bps: float = 8.0,
) -> dict:
    """Correlate local OHLC sweep candidates with nearby aggregate trades, sampled depth, OI and funding."""
    if market not in {"SPOT", "USD_M", "COIN_M"}:
        raise ValueError("market must be SPOT, USD_M or COIN_M")
    if interval not in {"1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d"}:
        raise ValueError("Unsupported candle interval")
    if not 30 <= limit <= 1000:
        raise ValueError("limit must be between 30 and 1000")
    if not 0.1 <= equal_level_tolerance_bps <= 100:
        raise ValueError("equal_level_tolerance_bps must be between 0.1 and 100")
    return _get(
        f"/api/v1/analysis/liquidity-sweep-confirmation/{market}/{quote(symbol.upper(), safe='')}",
        {"interval": interval, "limit": limit,
         "equal_level_tolerance_bps": equal_level_tolerance_bps},
    )


@mcp.tool()
@_reject_boolean_integer_arguments
def analyze_multi_timeframe_order_flow(
    market: str, symbol: str,
    periods: str = "5m,15m,1h,4h,1d",
    bin_size_bps: float = 5.0, value_area_pct: float = 70.0,
) -> dict:
    """Compare locally captured aggregate-trade CVD and volume-profile context across rolling timeframes."""
    if market not in {"SPOT", "USD_M", "COIN_M"}:
        raise ValueError("market must be SPOT, USD_M or COIN_M")
    selected = [item.strip() for item in periods.split(",") if item.strip()]
    allowed = {"5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d"}
    if not selected or len(selected) > 9 or len(set(selected)) != len(selected):
        raise ValueError("Select 1 to 9 unique timeframes")
    if any(item not in allowed for item in selected):
        raise ValueError("Unsupported timeframe")
    if not 0.1 <= bin_size_bps <= 500:
        raise ValueError("bin_size_bps must be between 0.1 and 500")
    if not 50 <= value_area_pct <= 99:
        raise ValueError("value_area_pct must be between 50 and 99")
    return _get(
        f"/api/v1/analysis/order-flow/multi-timeframe/{market}/{quote(symbol.upper(), safe='')}",
        {"periods": ",".join(selected), "bin_size_bps": bin_size_bps,
         "value_area_pct": value_area_pct},
    )




if __name__ == "__main__":
    # stdio transport keeps the adapter local to its configured AI client process.
    mcp.run(transport="stdio")
