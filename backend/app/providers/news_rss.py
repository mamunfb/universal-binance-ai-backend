from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

import httpx


def parse_feed_sources(raw: str) -> list[dict[str, str]]:
    """Parse NEWS_RSS_FEEDS as semicolon-separated 'name=url' entries."""
    sources: list[dict[str, str]] = []
    for entry in raw.split(";"):
        entry = entry.strip()
        if not entry or "=" not in entry:
            continue
        name, url = entry.split("=", 1)
        name, url = name.strip(), url.strip()
        parsed = urlparse(url)
        if name and parsed.scheme == "https" and parsed.netloc:
            sources.append({"name": name, "url": url})
    return sources


def _text(parent: ET.Element, names: tuple[str, ...]) -> str | None:
    for child in parent.iter():
        local = child.tag.rsplit("}", 1)[-1].lower()
        if local in names and child.text and child.text.strip():
            return child.text.strip()
    return None


def _parse_datetime(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(value)
        except (TypeError, ValueError, OverflowError):
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def parse_feed(xml_content: str, source_name: str, source_url: str) -> list[dict[str, Any]]:
    """Parse common RSS 2.0 and Atom feed entries without executing feed content."""
    root = ET.fromstring(xml_content)
    items = [
        node for node in root.iter()
        if node.tag.rsplit("}", 1)[-1].lower() in {"item", "entry"}
    ]
    parsed_items: list[dict[str, Any]] = []
    for item in items:
        title = _text(item, ("title",))
        link = _text(item, ("link", "id"))
        if not link:
            for child in item:
                if child.tag.rsplit("}", 1)[-1].lower() == "link":
                    link = child.attrib.get("href")
                    if link:
                        break
        if not title or not link:
            continue
        published = _text(item, ("pubdate", "published", "updated", "date"))
        summary = _text(item, ("description", "summary", "content"))
        parsed_items.append({
            "title": title[:500],
            "url": link[:2000],
            "summary": summary[:4000] if summary else None,
            "published_at": _parse_datetime(published),
            "source_name": source_name,
            "source_url": source_url,
        })
    return parsed_items


class RSSNewsProvider:
    def __init__(self, timeout_seconds: float = 15.0) -> None:
        self.timeout_seconds = timeout_seconds

    async def collect(
        self, sources: list[dict[str, str]], client: httpx.AsyncClient | None = None
    ) -> dict[str, Any]:
        owns_client = client is None
        if client is None:
            client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout_seconds),
                headers={"User-Agent": "universal-binance-ai-backend/0.1.0"},
                follow_redirects=True,
            )
        results: list[dict[str, Any]] = []
        failures: list[dict[str, str]] = []
        try:
            for source in sources:
                try:
                    response = await client.get(source["url"])
                    response.raise_for_status()
                    results.extend(parse_feed(response.text, source["name"], source["url"]))
                except Exception as exc:
                    # HTTP client exceptions can embed the full upstream URL,
                    # including userinfo, query tokens, and other credentials.
                    # Expose only a stable code and the non-sensitive exception class.
                    failures.append({
                        "source": source.get("name", "unknown"),
                        "error": "FEED_FETCH_FAILED",
                        "error_type": type(exc).__name__,
                    })
        finally:
            if owns_client:
                await client.aclose()
        return {
            "items": results,
            "successful_sources": len(sources) - len(failures),
            "failed_sources": len(failures),
            "failures": failures,
        }


def normalize_news_item(item: dict[str, Any]) -> dict[str, Any]:
    canonical = item["url"].strip()
    fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    host = urlparse(canonical).netloc.lower()
    return {
        **item,
        "id": fingerprint[:24],
        "source_domain": host,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "verification_status": "UNVERIFIED",
    }


def map_news_to_symbols(
    items: list[dict[str, Any]], symbols: list[str]
) -> list[dict[str, Any]]:
    """Conservative exact-token mapping; does not establish that a story is true."""
    normalized = sorted({s.upper() for s in symbols if re.fullmatch(r"[A-Z0-9]{2,20}", s.upper())})
    output = []
    for item in items:
        text = f"{item.get('title', '')} {item.get('summary') or ''}".upper()
        matches = [
            symbol for symbol in normalized
            if re.search(rf"(?<![A-Z0-9]){re.escape(symbol)}(?![A-Z0-9])", text)
        ]
        output.append({**item, "matched_symbols": matches,
                       "mapping_status": "MATCHED" if matches else "UNMAPPED"})
    return output
