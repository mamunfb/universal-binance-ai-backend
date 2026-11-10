# Stored Futures Account and Taker Ratios

## Supported observations

The service stores two USD-M Futures datasets returned by the Binance public futures data endpoints:

- `GLOBAL_LONG_SHORT`: `longShortRatio`, `longAccount`, `shortAccount`
- `TAKER_BUY_SELL`: `buySellRatio`, `buyVol`, `sellVol`

The data is stored in SQLite and uniquely keyed by market, ratio type, symbol, period and timestamp. Repeated collection for an existing timestamp updates that observation rather than duplicating it.

## Collection

```http
POST /api/v1/history/derivatives-ratios/USD_M/GLOBAL_LONG_SHORT/BTCUSDT/collect?period=1h&limit=500
POST /api/v1/history/derivatives-ratios/USD_M/TAKER_BUY_SELL/BTCUSDT/collect?period=1h&limit=500
```

## Read history

```http
GET /api/v1/history/derivatives-ratios/USD_M/GLOBAL_LONG_SHORT/BTCUSDT?period=1h&limit=200
GET /api/v1/history/derivatives-ratios/USD_M/TAKER_BUY_SELL/BTCUSDT?period=1h&limit=200
```

The MCP read tool is `get_stored_derivatives_ratio_history`. The MCP adapter does not trigger collection.

## Interpretation safeguards

Global long/short account ratio is based on account counts, not the size of positions held by those accounts. Taker buy/sell ratio describes aggressive buyer/seller volume in the sampled interval. Neither dataset reveals the identity of the party initiating every open position, represents every market participant, or guarantees subsequent price direction.

Collection is manual. No scheduled ratio collector or automatic historical backfill is included in this feature. The database begins accumulating records only after collection is run. Binance data availability and upstream limits apply; an empty response is returned as `NO_NEW_DATA`, not interpreted as a zero ratio.
