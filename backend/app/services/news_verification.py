from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from typing import Any
from urllib.parse import urlparse


def parse_domain_list(raw: str) -> set[str]:
    return {
        value.strip().lower().removeprefix("www.")
        for value in raw.split(",")
        if value.strip()
    }


def _domain(item: dict[str, Any]) -> str:
    value = item.get("source_domain") or urlparse(item.get("source_url") or item.get("url") or "").netloc
    return value.lower().removeprefix("www.").split(":")[0]


def _normalized_title(title: str) -> str:
    value = title.lower()
    value = re.sub(r"https?://\\S+", " ", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def _published(item: dict[str, Any]) -> datetime | None:
    value = item.get("published_at")
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def verify_news_items(
    items: list[dict[str, Any]],
    primary_domains: set[str],
    independent_domains: set[str],
    stale_after_hours: int = 168,
    similarity_threshold: float = 0.72,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Find cross-domain corroboration candidates; this is not factual adjudication."""
    current = now or datetime.now(timezone.utc)
    prepared = []
    for item in items:
        title = _normalized_title(item.get("title", ""))
        prepared.append({
            **item,
            "_title_key": title,
            "_domain": _domain(item),
            "_symbols": set(item.get("matched_symbols") or []),
        })

    output: list[dict[str, Any]] = []
    for index, item in enumerate(prepared):
        domain = item["_domain"]
        evidence: list[dict[str, Any]] = [{
            "source_name": item.get("source_name"),
            "source_domain": domain,
            "url": item.get("url"),
            "published_at": item.get("published_at"),
            "source_role": (
                "PRIMARY" if domain in primary_domains else
                "INDEPENDENT" if domain in independent_domains else "UNCLASSIFIED"
            ),
            "match_score": 1.0,
        }]
        primary_found = domain in primary_domains
        independent_found = domain in independent_domains
        for other_index, other in enumerate(prepared):
            if other_index == index or other["_domain"] == domain:
                continue
            if not item["_title_key"] or not other["_title_key"]:
                continue
            score = SequenceMatcher(None, item["_title_key"], other["_title_key"]).ratio()
            if score < similarity_threshold:
                continue
            if item["_symbols"] and other["_symbols"] and not (item["_symbols"] & other["_symbols"]):
                continue
            other_domain = other["_domain"]
            role = (
                "PRIMARY" if other_domain in primary_domains else
                "INDEPENDENT" if other_domain in independent_domains else "UNCLASSIFIED"
            )
            evidence.append({
                "source_name": other.get("source_name"),
                "source_domain": other_domain,
                "url": other.get("url"),
                "published_at": other.get("published_at"),
                "source_role": role,
                "match_score": round(score, 4),
            })
            primary_found = primary_found or role == "PRIMARY"
            independent_found = independent_found or role == "INDEPENDENT"

        published = _published(item)
        if published and published < current - timedelta(hours=stale_after_hours):
            status = "EXPIRED"
        elif primary_found and independent_found:
            status = "CONFIRMED"
        elif primary_found or independent_found:
            status = "PARTIALLY_CONFIRMED"
        else:
            status = "UNVERIFIED"

        clean_item = {key: value for key, value in item.items() if not key.startswith("_")}
        output.append({
            **clean_item,
            "verification_status": status,
            "verification_evidence": evidence,
            "verification_notes": (
                "CONFIRMED means a configured primary-domain item has a similar-title match "
                "from a configured independent domain. This automated corroboration signal "
                "does not prove every factual claim. FALSE is never assigned automatically."
            ),
        })
    return output
