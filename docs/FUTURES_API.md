# Binance Futures Market Data

The Futures provider uses public REST market-data endpoints and does not require API keys.

## Supported market families

- USDⓈ-M Futures: `https://fapi.binance.com/fapi/v1`
- COIN-M Futures: `https://dapi.binance.com/dapi/v1`

The scanner combines exchangeInfo symbol metadata with the 24-hour ticker response. It reports eligible, scanned, matched, and failed symbol counts. By default it includes TRADING perpetual contracts only. Set `perpetual_only=false` in the service layer to include other trading contract types.

## API endpoints

- `GET /api/v1/markets/futures/usdm/scan?quote_asset=USDT`
- `GET /api/v1/markets/futures/coinm/scan?quote_asset=USD`
- `GET /api/v1/markets/futures/usdm/klines/BTCUSDT?interval=1h&limit=500`
- `GET /api/v1/markets/futures/coinm/klines/BTCUSD_PERP?interval=1h&limit=500`

The exact symbols available depend on Binance exchange metadata at request time. COIN-M volume is reported in the exchange's quote-volume field; consumers should not assume it is directly comparable to USDⓈ-M volume without checking the contract and quote units.

## Limitations

This is market-data retrieval only. It does not retrieve private account positions, execute orders, or withdraw funds. It does not yet implement funding rates, open interest, liquidation streams, or order-book depth.
