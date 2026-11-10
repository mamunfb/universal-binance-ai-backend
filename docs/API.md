# Initial REST API

Run locally:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --app-dir backend --reload
```

On Windows PowerShell, activate with `.venv\\Scripts\\Activate.ps1`.

## Endpoints

### GET /health
Returns service health. This is a process health check, not an exchange connectivity check.

### GET /api/v1/markets/spot/scan
Scans Binance Spot symbols that are TRADING and use the requested quote asset.

Query parameters:
- `quote_asset`: quote asset, default `USDT`
- `min_quote_volume`: minimum 24-hour quote volume, default `0`

The response reports eligible, scanned, matched, and failed symbol counts. A result is marked INCOMPLETE if eligible symbols lack usable ticker data.

Example:
`GET /api/v1/markets/spot/scan?quote_asset=USDT&min_quote_volume=1000000`

### GET /api/v1/analysis/spot/technical/{symbol}
Fetches Spot klines and calculates EMA 20/50/200, Wilder RSI 14, MACD 12/26/9, and Bollinger Bands 20/2. Values are null when there is insufficient history. These are descriptive indicators, not guaranteed trading signals.

Example:
`GET /api/v1/analysis/spot/technical/BTCUSDT?interval=4h&limit=500`

### GET /api/v1/markets/spot/klines/{symbol}
Returns raw Binance Spot kline rows.

Query parameters:
- `interval`: supported Binance Spot interval
- `limit`: 1 to 1000, default 500

## Scope limitation
This first version only covers Binance Spot public endpoints. USDⓈ-M Futures, COIN-M Futures, news, on-chain data, order-book analytics, and technical indicator calculations are not implemented yet. Exchange responses are live and may be rate-limited or temporarily unavailable.


## Futures market data

See [FUTURES_API.md](./FUTURES_API.md) for USDⓈ-M and COIN-M market scanner and kline endpoints.
