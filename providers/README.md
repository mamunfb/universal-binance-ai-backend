# Data Providers

Provider adapters retrieve external data and normalize it into internal schemas.

Each provider must report:
- source name and endpoint/category
- retrieval timestamp (UTC)
- source timestamp where available
- symbols and markets covered
- successful, failed, and skipped requests
- missing fields and rate-limit conditions

Never silently substitute stale or missing data.
