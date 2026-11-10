from datetime import datetime, timezone

from app.services.news_verification import parse_domain_list, verify_news_items


def _item(title, domain, symbol="BTC", published="2026-11-10T10:00:00+00:00"):
    return {
        "title": title,
        "url": f"https://{domain}/story",
        "source_url": f"https://{domain}/feed",
        "source_domain": domain,
        "source_name": domain,
        "published_at": published,
        "matched_symbols": [symbol],
    }


def test_parse_domain_list_normalizes_domains():
    assert parse_domain_list("www.example.com, NEWS.example.org ") == {
        "example.com", "news.example.org"
    }


def test_primary_plus_independent_match_is_confirmed_with_evidence():
    items = [
        _item("Bitcoin ETF issuer announces major update", "official.example"),
        _item("Bitcoin ETF issuer announces major update today", "reporter.example"),
    ]
    result = verify_news_items(
        items, {"official.example"}, {"reporter.example"},
        now=datetime(2026, 11, 10, 11, tzinfo=timezone.utc),
    )
    assert all(item["verification_status"] == "CONFIRMED" for item in result)
    assert len(result[0]["verification_evidence"]) == 2


def test_single_configured_primary_is_partially_confirmed():
    result = verify_news_items(
        [_item("Bitcoin network upgrade announced", "official.example")],
        {"official.example"}, set(),
        now=datetime(2026, 11, 10, 11, tzinfo=timezone.utc),
    )
    assert result[0]["verification_status"] == "PARTIALLY_CONFIRMED"


def test_old_story_is_expired_even_if_it_has_multiple_sources():
    items = [
        _item("Bitcoin network upgrade announced", "official.example",
              published="2026-10-01T10:00:00+00:00"),
        _item("Bitcoin network upgrade announced", "reporter.example",
              published="2026-10-01T10:00:00+00:00"),
    ]
    result = verify_news_items(
        items, {"official.example"}, {"reporter.example"},
        now=datetime(2026, 11, 10, 11, tzinfo=timezone.utc),
    )
    assert all(item["verification_status"] == "EXPIRED" for item in result)


def test_unconfigured_sources_remain_unverified_and_false_is_never_guessed():
    result = verify_news_items(
        [_item("Bitcoin price moves today", "unknown.example")],
        set(), set(),
        now=datetime(2026, 11, 10, 11, tzinfo=timezone.utc),
    )
    assert result[0]["verification_status"] == "UNVERIFIED"
    assert "FALSE is never assigned automatically" in result[0]["verification_notes"]
