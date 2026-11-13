# AI Client API Permission Scope Proposal

Status: **proposal only — not implemented or enforced**

This document records a permission model for a future route-level authorization change. It does not grant, revoke, or assign permissions to ChatGPT, Gemini, Manus, Claude, Perplexity, or the owner key. No client-to-scope mapping has been approved.

## Current verified boundary

The API middleware authenticates configured owner/client Bearer keys and records the matched identity in `request.state.ai_client`. It does not currently enforce route-level scopes. Consequently, every successfully authenticated identity can reach the same API route surface.

The following three POST handlers are request-payload computations and do not call a persistence store or external provider in their handler/helper paths:

- `POST /api/v1/analysis/qualification-gates`
- `POST /api/v1/analysis/signal-lifecycle`
- `POST /api/v1/analysis/trade-risk-plan`

The helpers evaluate supplied values/timestamps or perform arithmetic. The trade-risk response explicitly sets `analysis_only: true` and `trading_enabled: false`.

The following operations have side effects and must not be silently grouped with stateless analysis:

- `POST /api/v1/history/market-confluence/snapshots`: persistent snapshot write.
- `POST /api/v1/history/funding-rates/USD_M/{symbol}/collect`: exchange data request plus persistent history write.
- `POST /api/v1/history/open-interest/USD_M/{symbol}/collect`: exchange data request plus persistent history write.
- `POST /api/v1/history/derivatives-ratios/USD_M/{ratio_type}/{symbol}/collect`: exchange data request plus persistent history write.
- `POST /api/v1/history/klines/{market}/{symbol}/collect`: exchange data request plus persistent history write.
- `POST /api/v1/onchain/evm/token/{contract}/index`: bounded EVM transfer-log retrieval plus local history indexing/storage.

These operations do not place exchange orders, sign transactions, withdraw funds, or execute trades.

## Proposed scope vocabulary

Scopes below are capability labels for design discussion, not existing runtime permissions.

| Proposed scope | Intended capability | Default stance |
|---|---|---|
| `market:read` | Read market, analysis, history, quality, and collector-status endpoints | Grant only to clients explicitly approved for research reads |
| `analysis:compute` | Run stateless, payload-based analysis utilities listed above | Separate from persistence and collection |
| `research:snapshot:write` | Save descriptive market-confluence snapshots | Deny unless explicitly approved |
| `history:collect` | Trigger exchange-history collection and storage | Deny unless explicitly approved |
| `onchain:index` | Retrieve and index EVM token transfer history | Deny unless explicitly approved |

## Required decisions before implementation

1. Confirm whether owner credentials are a superuser capability or should also be scope-limited.
2. Assign each named AI client only the scopes its operator explicitly approves. Do not infer a mapping from the client's name.
3. Decide whether analysis utilities should be separately allowed from ordinary read endpoints.
4. Decide whether snapshot writes, exchange-history collection, and EVM indexing require separate approval or may share a scope.
5. Define how missing, malformed, duplicate, or unknown client identities are handled. Recommended behavior is deny by default.
6. Decide whether scope configuration changes require restart, and how revocation takes effect.

## Implementation and regression requirements

When the policy is approved, enforce authorization centrally before route handlers execute. Do not rely on documentation, client identity recording, UI hiding, or MCP tool omission as access control.

Add tests covering:
- each identity with allowed and denied scopes;
- owner-key behavior;
- missing/unknown identity and malformed scope configuration;
- duplicate key matches;
- every side-effecting route, including no upstream call and no persistence when denied;
- all three stateless analysis POST routes under their approved policy;
- consistent machine-readable 401/403 responses.

Keep order placement, signing, withdrawals, and trade execution outside this proposal. No such capability is authorized by this document.

## Additional operational side effects found in the route/startup audit

The API route inventory in `backend/app/main.py` contains 82 declared application routes: 73 GET and 9 POST. **Do not use this count as an authorization guarantee**; the permission boundary must be based on each route's actual handler and dependencies. The explicit side-effecting POST routes are enumerated above. No PUT, PATCH, or DELETE route decorators were found in this file at the current audited revision.

Many GET endpoints are not necessarily local-only reads: market/news/on-chain endpoints can make outbound requests to public exchange, RSS, or configured EVM RPC providers. They do not thereby become database-write operations, but they can consume upstream quota, incur latency, or expose request metadata to those providers. A future policy may want a separate `upstream:read` capability or rate budget if that distinction is operationally important; this is a proposal, not current enforcement.

The application lifespan also starts optional background collectors from deployment settings, independently of any AI-client request:

- liquidation collector when `LIQUIDATION_COLLECTOR_ENABLED` is enabled;
- order-book stream collector when `ORDER_BOOK_COLLECTOR_ENABLED` is enabled;
- aggregate-trade collector when `AGGREGATE_TRADE_COLLECTOR_ENABLED` is enabled;
- derivatives history collector when `DERIVATIVES_COLLECTOR_ENABLED` is enabled;
- historical-kline collector when `HISTORICAL_COLLECTOR_ENABLED` is enabled.

These collectors can call external providers and persist observations. Route-level AI-client scopes do not control them. They require separate deployment-operator controls, explicit environment configuration, and operational monitoring. Do not treat a client scope denial as stopping a collector that is enabled at application startup.

## Audit caveats

This was a static source audit of the checked-out PR branch. It does not prove that every transitive helper is side-effect-free beyond the three named analysis helper implementations, nor does it validate live provider behavior, deployment environment values, or production collector state. Re-audit helper call graphs and deployment configuration before enabling a production permission policy.

## Background collector lifecycle findings

All five collector enable flags in `backend/app/config.py` default to `False`. When enabled, `backend/app/main.py` starts collector tasks during FastAPI lifespan startup. These are process-local tasks, not a separately coordinated distributed worker service.

Operational implications:

- Run collector-enabled application deployments as a single collector-owning process per configured job set unless a distributed lease/leader-election mechanism is added.
- Multiple web replicas with the same collector flags and job configuration may each open streams or poll the same upstream endpoints. Storage uniqueness may reduce duplicate rows in some stores, but it does not prevent duplicate network traffic, provider quota use, or CPU.
- The historical-kline collector status response explicitly warns that it runs only while the application process is alive and recommends one collector process per database. Equivalent deployment guidance should be made consistent for all collectors.
- Collector task status is process-local. A status response from one replica does not establish the state of collectors on another replica.
- The lifespan startup sequence is now inside `try/finally`, so a later collector constructor/startup failure triggers cleanup for collectors already started. Regression coverage is in `tests/test_collector_lifespan.py`.
- Shutdown now attempts all enabled collector stops with `asyncio.gather(..., return_exceptions=True)` and logs per-collector failures, so one failing stop does not prevent the remaining stop attempts. This does not yet guarantee a hard shutdown deadline if an individual collector's `stop()` hangs; bounded shutdown/timeouts remain a follow-up.

Recommended follow-up tests (not yet implemented by this documentation change):
1. Add coverage that disabled flags start no collector tasks.
2. Add coverage that shutdown attempts every collector even when one stop operation raises.
3. Add bounded-shutdown behavior so a stuck collector cannot indefinitely delay service termination.
4. Status endpoints should distinguish disabled, starting, running, degraded, disconnected, and stopped states accurately.
5. Keep the single collector-owner process requirement explicit until distributed coordination exists.
