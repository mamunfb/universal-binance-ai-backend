# COIN-M Inverse Risk Calculation

The COIN-M branch of \`POST /api/v1/analysis/trade-risk-plan\` uses the inverse contract model. It is separate from Spot cash sizing and linear USD-M sizing.

## Required inputs

- \`market: "COIN_M"\`
- \`direction: "LONG" | "SHORT"\`
- \`entry_price\`, \`stop_loss\`, and one to three \`take_profits\`
- \`contract_size_usd\`: fixed USD face value per contract, sourced from the COIN-M exchange information \`contractSize\` field
- \`settlement_asset\`: the contract's margin/settlement asset, normally sourced from \`marginAsset\`
- \`fee_rate_per_side\`, \`slippage_bps_per_side\`, and \`adverse_funding_cost_percent\` to calculate net R/R

For optional position sizing, \`account_capital\` must be denominated in the settlement asset (for example BTC for BTCUSD COIN-M), and \`risk_percent\` must also be supplied. \`max_notional\`, when supplied, is a USD notional cap.

## Inverse PnL formula

For one fixed-USD-face-value contract:

\`PnL(settlement coin) = contract_size_usd × direction × (1 / entry_price − 1 / exit_price)\`

Direction is +1 for LONG and -1 for SHORT. This is the inverse COIN-M calculation described in Binance's PnL guidance.

Gross risk per contract is the absolute PnL at the stop. Gross reward per contract is the PnL at each take-profit target.

The implementation estimates each side's fee and slippage cost in settlement coin using that side's USD face value divided by its execution price. The adverse funding input is interpreted as the **total** adverse funding cost over the planned holding period, expressed as a percentage of entry USD notional. This is an explicit user-supplied scenario assumption, not a forecast of future funding.

Net risk/reward is withheld unless fee, slippage and adverse funding assumptions are all supplied.

## Important limitations

- The calculator does not fetch a live mark price or current funding estimate.
- It does not calculate liquidation price. That requires, among other things, leverage, margin mode, wallet balance/position context and the correct maintenance-margin tier.
- It does not apply exchange quantity step size, minimum quantity/notional or precision filters to the calculated contract count.
- It does not model partial fills, order-book impact, changing funding rates, insurance/ADL events or contract delivery settlement.
- It does not place, amend or cancel orders.
- The result is arithmetic for a user-supplied scenario, not a live trade signal or financial advice.

## Primary references

- Binance support: [How to Calculate Profit and Loss for Futures Contracts](https://www.binance.bh/en-IN/support/faq/detail/3a55a23768cb416fb404f06ffedde4b2)
- Binance COIN-M API: [Get Funding Info / contract metadata](https://developers.binance.com/docs/derivatives/coin-margined-futures/market-data/rest-api/Get-Funding-Info)
- Binance support: [How to Calculate Liquidation Price of Coin-M Futures Contracts](https://www.binance.com/en-IN/support/faq/detail/ceccfcfb4e3a45e3b48b0b1bb1a8ae46)
