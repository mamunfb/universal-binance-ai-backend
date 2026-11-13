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
