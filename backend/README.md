# Backend

The backend will provide normalized data and the analysis API.

## Implementation sequence
1. Define configuration and environment handling.
2. Add a health endpoint.
3. Add a Binance public market-data provider.
4. Normalize exchange responses and timestamps.
5. Add indicator calculations with tests.
6. Add coverage and data-quality reporting.
7. Add REST endpoints.
8. Add caching and persistence when needed.

Do not add exchange credentials for public market-data endpoints. Keep secrets out of source control.
