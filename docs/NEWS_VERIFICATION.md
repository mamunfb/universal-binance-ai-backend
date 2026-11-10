# News Verification Engine — first implementation

## Configuration

Classify feed publisher domains explicitly; do not infer that a domain is official from its name.

```dotenv
NEWS_PRIMARY_SOURCE_DOMAINS=bitcoin.org,binance.com
NEWS_INDEPENDENT_SOURCE_DOMAINS=reuters.com,coindesk.com
NEWS_STALE_AFTER_HOURS=168
```

Use only domains you have manually checked and are entitled to access. A domain may be incorrectly classified if the operator configures it incorrectly. Subdomains are not automatically promoted to a parent domain.

## Verification rules

- CONFIRMED: the item comes from a configured primary domain and a similar-title candidate appears on a different configured independent domain.
- PARTIALLY_CONFIRMED: a configured primary or independent domain is represented, but both classes are not present.
- UNVERIFIED: no configured primary/independent source supports the item.
- EXPIRED: publication timestamp is older than the configured age threshold.
- FALSE: never assigned automatically. A future human-review workflow must preserve the contradictory evidence and reviewer provenance.

The engine uses title similarity and ticker overlap as a candidate matching heuristic. It does not compare full factual claims, prove source independence, validate the publisher's identity, or establish truth. Syndicated copies may appear on separate domains. Therefore even CONFIRMED means corroborated by configured source classes, not guaranteed true.

Missing or unparseable publication timestamps are not marked expired. An empty source-class configuration does not make any item verified.

## Threshold

The current default title similarity threshold is 0.72 using Python SequenceMatcher. This is a heuristic, not a calibrated probability. It should be evaluated against a labeled dataset before changing or relying on it.
