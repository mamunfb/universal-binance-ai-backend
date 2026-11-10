import httpx

from app.providers.news_rss import RSSNewsProvider, map_news_to_symbols, parse_feed, parse_feed_sources
from app.services.news_intelligence import collect_news_intelligence


RSS = """<?xml version="1.0"?>
<rss version="2.0"><channel><item>
<title>Bitcoin BTC market update</title>
<link>https://news.example.test/btc-update</link>
<pubDate>Tue, 10 Nov 2026 10:00:00 GMT</pubDate>
<description>BTC volatility increased.</description>
</item></channel></rss>"""


ATOM = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom"><entry>
<title>Ethereum ETH upgrade</title>
<link href="https://news.example.test/eth" rel="alternate"/>
<updated>2026-11-10T10:00:00Z</updated>
<summary>ETH network upgrade.</summary>
</entry></feed>"""


def test_parse_feed_sources_accepts_only_https():
    sources = parse_feed_sources("Trusted=https://example.com/rss;Bad=http://bad.test/rss")
    assert sources == [{"name": "Trusted", "url": "https://example.com/rss"}]


def test_parse_rss_and_atom():
    rss = parse_feed(RSS, "Example", "https://example.test/rss")
    atom = parse_feed(ATOM, "Atom", "https://example.test/atom")
    assert rss[0]["title"] == "Bitcoin BTC market update"
    assert rss[0]["published_at"] == "2026-11-10T10:00:00+00:00"
    assert atom[0]["url"] == "https://news.example.test/eth"
    assert atom[0]["title"] == "Ethereum ETH upgrade"


def test_symbol_mapping_uses_exact_tokens():
    items = [{"title": "BTC rally, not XBTC", "summary": "ETH also mentioned"}]
    mapped = map_news_to_symbols(items, ["BTC", "ETH"])
    assert mapped[0]["matched_symbols"] == ["BTC", "ETH"]


async def test_collect_news_marks_items_unverified_and_reports_coverage():
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text=RSS))
    async with httpx.AsyncClient(transport=transport) as client:
        provider = RSSNewsProvider()
        fetched = await provider.collect(
            [{"name": "Example", "url": "https://example.test/rss"}], client=client
        )
    assert fetched["successful_sources"] == 1
    assert len(fetched["items"]) == 1

    # Service-level behavior uses the provider interface and retains conservative status.
    class FakeProvider:
        async def collect(self, sources):
            return {"items": fetched["items"], "successful_sources": 1,
                    "failed_sources": 0, "failures": []}

    result = await collect_news_intelligence(
        FakeProvider(), [{"name": "Example", "url": "https://example.test/rss"}], ["BTC"]
    )
    assert result["status"] == "COMPLETED"
    assert result["items"][0]["verification_status"] == "UNVERIFIED"
    assert result["items"][0]["matched_symbols"] == ["BTC"]


async def test_no_sources_is_blocked_not_empty_success():
    result = await collect_news_intelligence(RSSNewsProvider(), [], ["BTC"])
    assert result["status"] == "BLOCKED"
    assert result["returned_count"] == 0


async def test_feed_failure_does_not_expose_secret_query_parameters():
    url = "https://feeds.example.test/rss?token=feed-secret"
    transport = httpx.MockTransport(lambda request: httpx.Response(503, request=request))
    async with httpx.AsyncClient(transport=transport) as client:
        result = await RSSNewsProvider().collect([{"name": "Private feed", "url": url}], client=client)
    assert result["failed_sources"] == 1
    assert result["failures"][0]["error"] == "HTTPStatusError"
    assert "feed-secret" not in str(result["failures"])
