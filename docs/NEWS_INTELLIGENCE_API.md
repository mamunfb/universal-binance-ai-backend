# News Intelligence API (RSS/Atom ingestion — first stage)

## Configuration

Set `NEWS_RSS_FEEDS` as a semicolon-separated list of named HTTPS feed URLs:

```dotenv
NEWS_RSS_FEEDS=Project Blog=https://example.org/feed.xml;Industry News=https://example.net/rss
```

Only HTTPS URLs are accepted. The repository does not silently scrape undocumented Binance announcement pages or claim a complete news universe. Add feeds only after checking that the publisher provides the feed and permits its use.

## Endpoint

`GET /api/v1/news/intelligence?symbols=BTC,ETH&hours=72&limit=100`

- `symbols`: comma-separated ticker tokens to match (default BTC,ETH)
- `hours`: lookback window, 1–720 (default 72)
- `limit`: maximum returned items, 1–500 (default 100)

The first implementation supports RSS 2.0 and Atom. It normalizes titles, URLs, summaries, publication timestamps, source domains, and fetch timestamps. Exact URL duplicates are removed. Ticker matching uses exact token boundaries and is only a relevance hint, not proof that the article is about a specific asset.

## Status and limitations

- `COMPLETED`: every configured feed was fetched successfully.
- `INCOMPLETE`: at least one configured feed failed.
- `BLOCKED`: no feeds were configured.
- Every item passes through a conservative cross-source matching stage. Configure primary and independent publisher domains as described in NEWS_VERIFICATION.md. A matching primary plus independent domain yields CONFIRMED as an automated corroboration signal, not proof of factual truth; single-class evidence yields PARTIALLY_CONFIRMED; unclassified sources remain UNVERIFIED; old dated items become EXPIRED. FALSE is never assigned automatically.
- Missing or unparseable publication dates are retained but cannot be reliably age-filtered.
- URL deduplication is exact only; semantic duplicate detection is not implemented.
- No global news coverage, sentiment score, catalyst score, or trading probability is claimed.

## Source policy

Prefer primary sources: official project blogs, official exchange announcements, protocol governance posts, and regulator releases. Add reputable independent reporting as a separate source for corroboration. Verification evidence preserves the matching source domains, URLs, timestamps, and heuristic match scores. Read NEWS_VERIFICATION.md for configuration and limitations. Never treat automated corroboration as proof that every claim is true.
