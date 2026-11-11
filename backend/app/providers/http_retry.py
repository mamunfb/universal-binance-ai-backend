"""Bounded retry handling for idempotent Binance public-data GET requests."""

import asyncio
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import httpx


def _retry_after_seconds(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError, OverflowError):
        pass
    try:
        retry_at = parsedate_to_datetime(value)
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=timezone.utc)
        return max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds())
    except (TypeError, ValueError, OverflowError):
        return None


async def get_json_with_retry(
    client: httpx.AsyncClient,
    path: str,
    params: dict[str, Any] | None = None,
    *,
    max_attempts: int = 3,
    base_delay_seconds: float = 0.25,
    max_backoff_seconds: float = 4.0,
) -> Any:
    """GET JSON with bounded retries for transient failures and Binance rate limits.

    HTTP 429 honors Retry-After (or uses exponential backoff if the header is absent).
    HTTP 418 is an IP-ban response and is raised immediately without another request.
    Only idempotent GET requests are passed through this helper.
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")
    if base_delay_seconds < 0 or max_backoff_seconds < 0:
        raise ValueError("retry delays must be non-negative")

    for attempt in range(max_attempts):
        try:
            response = await client.get(path, params=params)
        except httpx.TransportError:
            if attempt + 1 >= max_attempts:
                raise
            delay = min(base_delay_seconds * (2 ** attempt), max_backoff_seconds)
            await asyncio.sleep(delay)
            continue

        status = response.status_code
        if status == 418:
            response.raise_for_status()
        if status == 429 or 500 <= status <= 599:
            if attempt + 1 >= max_attempts:
                response.raise_for_status()
            retry_after = _retry_after_seconds(response.headers.get("Retry-After"))
            delay = retry_after if retry_after is not None else min(
                base_delay_seconds * (2 ** attempt), max_backoff_seconds
            )
            await asyncio.sleep(delay)
            continue

        response.raise_for_status()
        return response.json()

    raise RuntimeError("Binance request retry loop ended unexpectedly")
