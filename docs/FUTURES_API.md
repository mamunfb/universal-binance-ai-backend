# Binance Futures Market Data

The Futures provider uses public REST market-data endpoints and does not require API keys.

## Supported market families

- USDⓈ-M Futures: `https://fapi.binance.com/fapi/v1`
- COIN-M Futures: `https://dapi.binance.com/dapi/v1`

The scanner combines exchangeInfo symbol metadata with the 24-hour ticker response. It reports eligible, scanned, matched, and failed symbol counts. By default it includes all TRADING contract types returned by exchangeInfo, including perpetual and currently trading dated contracts. Set `perpetual_only=true` only when intentionally narrowing the scan.

## API endpoints

- `GET /api/v1/markets/futures/usdm/scan?quote_asset=USDT`
- `GET /api/v1/markets/futures/coinm/scan?quote_asset=USD`
- `GET /api/v1/markets/futures/usdm/klines/BTCUSDT?interval=1h&limit=500`
- `GET /api/v1/markets/futures/coinm/klines/BTCUSD_PERP?interval=1h&limit=500`

The exact symbols available depend on Binance exchange metadata at request time. USDⓈ-M ticker quote volume is returned by Binance. For COIN-M, where the ticker response supplies base-asset volume rather than a quote-volume field, the scanner derives a quote-notional proxy as `baseVolume × lastPrice` and labels it `DERIVED_BASE_VOLUME_TIMES_LAST_PRICE`. This is a calculated estimate, not a native exchange quote-volume observation; do not compare it blindly with USDⓈ-M quote volume or treat it as contract count.

## Limitations

This is market-data retrieval only. It does not retrieve private account positions, execute orders, or withdraw funds. It does not yet implement funding rates, open interest, liquidation streams, or order-book depth.
