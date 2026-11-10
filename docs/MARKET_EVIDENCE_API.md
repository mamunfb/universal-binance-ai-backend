# Unified Market Evidence Snapshot

## Endpoint

`GET /api/v1/analysis/market-evidence/{symbol}`

This read-only research endpoint combines the following existing sources for one symbol:

- Binance Spot multi-timeframe trend structure (15m, 1h, 4h, 1d).
- Latest Spot and USDⓈ-M Futures price basis and latest funding record.
- USDⓈ-M current open interest and historical change across the returned sample, global long/short account ratio, taker buy/sell ratio, and order-book snapshot.
- Spot 1h OHLCV-based VWAP, approximate volume profile, and rule-based market structure.
- Configured RSS/Atom news catalyst triage and corroboration status.

## Response interpretation

The response has an overall `COMPLETED` status only when every required section reports completed. Otherwise it is `INCOMPLETE`, while available evidence is still returned with per-section status and limitations.

The `evidence` array contains descriptive observations. It does not rank assets, calculate a validated probability, or generate Buy/Sell instructions. The `decision` object deliberately returns:

- `status: NO_TRADE_DECISION`
- `buy_sell_signal: null`
- `probability: null`

News candidates are included for signal review only when their item-level verification status is `CONFIRMED` and the existing catalyst rules mark them eligible. Automated corroboration is not proof of truth. A feed failure keeps the news evidence status `INCOMPLETE`, even if some candidate items were returned.

## Important limitations

- Sources are requested concurrently and are not an atomic exchange snapshot; timestamps can differ.
- The endpoint currently uses Binance Spot and USDⓈ-M Futures, not cross-exchange market breadth.
- Funding, account ratios, taker ratios, open-interest changes and order-book depth have distinct meanings and must not be collapsed into a single directional indicator. Open-interest growth alone does not identify whether new positions are long or short.
- OHLCV volume profile assigns each candle's volume to a typical-price bin; it is an approximation, not trade-level volume-at-price.
- News coverage is limited to configured feeds. Keyword rules and configured independent-source corroboration are triage aids, not factual guarantees or price-impact measurements.
- Missing or incomplete evidence must not be interpreted as zero activity or as confirmation of a thesis.

This endpoint is research-only and does not place orders, sign transactions, or execute trades.
