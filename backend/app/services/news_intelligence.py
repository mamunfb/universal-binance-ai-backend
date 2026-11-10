from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.providers.news_rss import RSSNewsProvider, map_news_to_symbols, normalize_news_item


def _within_window(item: dict[str, Any], cutoff: datetime) -> bool:
    published = item.get("published_at")
    if not published:
        return True
    try:
        parsed = datetime.fromisoformat(published.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed >= cutoff
    except (TypeError, ValueError):
        return True


async def collect_news_intelligence(
    provider: RSSNewsProvider,
    sources: list[dict[str, str]],
    symbols: list[str],
    hours: int = 72,
    limit: int = 100,
) -> dict[str, Any]:
    fetched = await provider.collect(sources)
    normalized = [normalize_news_item(item) for item in fetched["items"]]
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    fresh = [item for item in normalized if _within_window(item, cutoff)]
    # URL fingerprints remove exact duplicate links across feeds; no semantic deduplication claimed.
    unique: dict[str, dict[str, Any]] = {}
    for item in fresh:
        unique.setdefault(item["id"], item)
    mapped = map_news_to_symbols(list(unique.values()), symbols)
    mapped.sort(key=lambda item: item.get("published_at") or "", reverse=True)
    status = "COMPLETED" if sources and fetched["failed_sources"] == 0 else (
        "INCOMPLETE" if sources else "BLOCKED"
    )
    return {
        "status": status,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window_hours": hours,
        "configured_source_count": len(sources),
        "successful_source_count": fetched["successful_sources"],
        "failed_source_count": fetched["failed_sources"],
        "failure_details": fetched["failures"],
        "raw_item_count": len(fetched["items"]),
        "unique_url_count": len(unique),
        "returned_count": min(len(mapped), limit),
        "items": mapped[:limit],
        "verification_policy": (
            "Every item remains UNVERIFIED. Feed presence is not independent confirmation; "
            "verification and catalyst classification are separate future stages."
        ),
        "coverage_warning": (
            "Only configured RSS/Atom feeds were queried. This is not a complete global news scan. "
            "Exact URL duplicates are removed; semantic duplicates are not."
        ),
    }
