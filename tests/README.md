# Tests

Tests should cover:
- provider response parsing and schema validation
- timestamp and freshness handling
- indicator calculations against known fixtures
- market-universe coverage accounting
- missing-data and failure reporting
- risk calculations and edge cases

Use recorded fixtures for deterministic tests. Do not depend on live exchange responses for every unit test.
