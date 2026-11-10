from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.providers.news_rss import RSSNewsProvider, map_news_to_symbols, normalize_news_item
from app.services.news_verification import verify_news_items


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
    primary_domains: set[str] | None = None,
    independent_domains: set[str] | None = None,
    stale_after_hours: int = 168,
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
    verified = verify_news_items(
        mapped,
        primary_domains=primary_domains or set(),
        independent_domains=independent_domains or set(),
        stale_after_hours=stale_after_hours,
    )
    verified.sort(key=lambda item: item.get("published_at") or "", reverse=True)
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
        "returned_count": min(len(verified), limit),
        "verification_status_counts": {
            label: sum(1 for item in verified if item["verification_status"] == label)
            for label in ("CONFIRMED", "PARTIALLY_CONFIRMED", "UNVERIFIED", "EXPIRED", "FALSE")
        },
        "items": verified[:limit],
        "verification_policy": (
            "CONFIRMED means a configured primary-domain item has a similar-title candidate "
            "from a configured independent domain. It is an automated corroboration signal, "
            "not proof of factual truth. FALSE is never assigned automatically."
        ),
        "coverage_warning": (
            "Only configured RSS/Atom feeds were queried. This is not a complete global news scan. "
            "Exact URL duplicates are removed; semantic duplicates are not."
        ),
    }
