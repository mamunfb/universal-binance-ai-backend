"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");

global.window = {};
require("../dashboard/chart.js");
const charts = global.window.DashboardCharts;

function candle(time, close, options = {}) {
  const open = options.open ?? close;
  const high = options.high ?? Math.max(open, close) + 1;
  const low = options.low ?? Math.min(open, close) - 1;
  return [time, open, high, low, close, options.volume ?? 10, time + 3599999];
}

test("VWAP remains finite when individually finite candle volumes overflow their raw sum", () => {
  const candles = [
    {time:1,open:10,high:12,low:9,close:11,volume:Number.MAX_VALUE,closeTime:2},
    {time:3,open:20,high:22,low:19,close:21,volume:Number.MAX_VALUE,closeTime:4}
  ];
  const result = charts.indicators(candles);
  assert.equal(result.vwap, 16);
  assert.ok(Number.isFinite(result.vwap));
});

test("parse sorts valid OHLCV rows and rejects null, malformed and impossible candles", () => {
  const parsed = charts.parse([
    candle(3600000, 102),
    candle(0, 100),
    [7200000, null, 10, 9, 10, 2, 10799999],
    [10800000, 10, 8, 9, 10, 2, 14399999],
    [14400000, 10, 11, 9, 10, -1, 17999999],
    [18000000, 10, 11, 9, 10, 1, null]
  ]);
  assert.deepEqual(parsed.map(row => row.time), [0, 3600000]);
  assert.equal(parsed[0].close, 100);
});

test("parse rejects unsafe and out-of-range JavaScript date timestamps", () => {
  const parsed = charts.parse([
    candle(Number.MAX_SAFE_INTEGER + 1, 100),
    [8640000000000001, 100, 101, 99, 100, 1, 8640000000000001],
    [0, 100, 101, 99, 100, 1, Number.MAX_SAFE_INTEGER + 1],
    candle(3600000, 102)
  ]);
  assert.deepEqual(parsed.map(row => row.time), [3600000]);
});

test("parse rejects whitespace-only numeric fields and all duplicate candle timestamps", () => {
  const parsed = charts.parse([
    candle(0, 100),
    candle(0, 101),
    candle(3600000, 102),
    [7200000, 100, 101, 99, 100, "   ", 10799999]
  ]);
  assert.deepEqual(parsed.map(row => row.time), [3600000]);
});


test("parse handles a large reversed candle batch and removes only duplicated timestamps", () => {
  const rows = Array.from({length:10000}, (_,i) => candle(i*3600000, 100+i/100));
  rows.push(candle(5000*3600000, 999));
  const parsed = charts.parse(rows.reverse());
  assert.equal(parsed.length, 9999);
  assert.equal(parsed[0].time, 0);
  assert.equal(parsed.at(-1).time, 9999*3600000);
  assert.ok(parsed.every((row,i) => i===0 || row.time>parsed[i-1].time));
});

test("3h aggregation rejects buckets whose summed volume overflows to Infinity", () => {
  const rows = [0, 3600000, 7200000].map(time => ({time,open:100,high:102,low:99,close:101,volume:Number.MAX_VALUE,closeTime:time+3599999}));
  assert.deepEqual(charts.aggregate3h(rows), []);
});

test("3h aggregation scales across many complete buckets and discards a missing-hour bucket", () => {
  const rows = Array.from({length:3000}, (_,i) => candle(i*3600000, 100+i/100));
  const withGap = rows.filter(row => row[0] < 1500*3600000 || row[0] >= 1501*3600000);
  const aggregated = charts.aggregate3h(rows.map(row => ({time:row[0],open:row[1],high:row[2],low:row[3],close:row[4],volume:row[5],closeTime:row[6]})));
  const gapAggregated = charts.aggregate3h(withGap.map(row => ({time:row[0],open:row[1],high:row[2],low:row[3],close:row[4],volume:row[5],closeTime:row[6]})));
  assert.equal(aggregated.length, 1000);
  assert.equal(gapAggregated.length, 999);
  assert.ok(aggregated.every((row,i) => i===0 || row.time>aggregated[i-1].time));
});

test("3h aggregation combines exactly three UTC-aligned consecutive hourly candles", () => {
  const rows = [candle(0, 101, {open:100, high:103, low:99, volume:2}),
    candle(3600000, 102, {open:101, high:104, low:100, volume:3}),
    candle(7200000, 103, {open:102, high:105, low:101, volume:4})];
  const result = charts.aggregate3h(rows);
  assert.equal(result.length, 1);
  assert.deepEqual(result[0], {time:0,open:100,high:105,low:99,close:103,volume:9,closeTime:10799999});
});

test("3h aggregation discards incomplete, duplicated and misaligned buckets", () => {
  const incomplete = [candle(0, 101), candle(3600000, 102)];
  const duplicate = [candle(0, 101), candle(0, 102), candle(3600000, 103), candle(7200000, 104)];
  const misaligned = [candle(60000, 101), candle(3660000, 102), candle(7260000, 103)];
  assert.equal(charts.aggregate3h(incomplete).length, 0);
  assert.equal(charts.aggregate3h(duplicate).length, 0);
  assert.equal(charts.aggregate3h(misaligned).length, 0);
  const invalidCloseTime = [candle(0, 101), candle(3600000, 102), candle(7200000, 103)].map(row => ({time:row[0],open:row[1],high:row[2],low:row[3],close:row[4],volume:row[5],closeTime:row[6]}));
  invalidCloseTime[1].closeTime += 1;
  assert.equal(charts.aggregate3h(invalidCloseTime).length, 0);
});

test("timeframe and market route mapping stays explicit", () => {
  assert.equal(charts.intervalFor("3h"), "1h");
  assert.equal(charts.intervalFor("1D"), "1d");
  assert.equal(charts.intervalFor("3D"), "3d");
  assert.equal(charts.intervalFor("1W"), "1w");
  assert.equal(charts.intervalFor("1M"), "1M");
  assert.equal(charts.routeFor("SPOT"), "/api/v1/markets/spot/klines/");
  assert.equal(charts.routeFor("USD_M"), "/api/v1/markets/futures/usdm/klines/");
  assert.equal(charts.routeFor("COIN_M"), "/api/v1/markets/futures/coinm/klines/");
  assert.equal(charts.routeFor("UNKNOWN"), null);
});

test("EMA seeds with the initial SMA and applies the recursive smoothing factor", () => {
  const result = charts.emaSeries([1,2,3,4,5],3);
  assert.deepEqual(result.slice(0,2),[null,null]);
  assert.deepEqual(result.slice(2),[2,3,4]);
});

test("Wilder RSI and ATR match hand-calculated gain-loss and true-range fixtures", () => {
  const rsi = charts.rsiSeries([1,2,3,2,4],2);
  assert.equal(rsi[2],100);
  assert.equal(rsi[3],50);
  assert.ok(Math.abs(rsi[4]-(100-100/(1+1.25/0.25)))<1e-12);
  const candles = [
    {time:0,open:10,high:11,low:9,close:10,volume:1,closeTime:3599999},
    {time:3600000,open:10,high:12,low:10,close:11,volume:1,closeTime:7199999},
    {time:7200000,open:11,high:15,low:11,close:14,volume:1,closeTime:10799999},
    {time:10800000,open:14,high:20,low:14,close:19,volume:1,closeTime:14399999}
  ];
  const atr = charts.atrSeries(candles,2);
  assert.equal(atr[2],3);
  assert.equal(atr[3],4.5);
});

test("flat price RSI is neutral and ATR uses Wilder smoothing", () => {
  const flat = Array.from({length:16}, (_,i) => ({time:i*3600000,open:100,high:101,low:99,close:100,volume:1,closeTime:i*3600000+3599999}));
  const result = charts.indicators(flat);
  assert.equal(result.rsi_14_wilder, 50);
  assert.equal(result.atr_14_wilder, 2);
  assert.equal(result.candle_count, 16);
  assert.match(result.method, /not a validated trading signal/);
});

test("indicator series align to candles and expose MACD line, signal and histogram", () => {
  const values = Array.from({length:80}, (_,i) => 100 + Math.sin(i/5)*4 + i*0.08);
  const rsi = charts.rsiSeries(values);
  const atrCandles = values.map((close,i) => ({time:i*3600000,open:close-0.2,high:close+1,low:close-1,close,volume:10,closeTime:i*3600000+3599999}));
  const atr = charts.atrSeries(atrCandles);
  const macd = charts.macdComponents(values);
  assert.equal(rsi.length, values.length);
  assert.equal(atr.length, values.length);
  assert.equal(macd.line.length, values.length);
  assert.equal(macd.signal.length, values.length);
  assert.equal(macd.histogram.length, values.length);
  assert.ok(rsi.slice(14).every(v => Number.isFinite(v) && v >= 0 && v <= 100));
  assert.ok(macd.histogram.slice(33).every(v => Number.isFinite(v)));
});

test("MACD signal and histogram are derived from the aligned MACD line", () => {
  const values = Array.from({length:90}, (_,i) => 80 + i*0.15 + Math.sin(i/4)*3);
  const result = charts.macdComponents(values);
  assert.equal(result.line.length, values.length);
  assert.equal(result.signal.length, values.length);
  assert.equal(result.histogram.length, values.length);
  assert.ok(result.line.slice(25).every(Number.isFinite));
  assert.ok(result.signal.slice(33).every(Number.isFinite));
  for (let i=33;i<values.length;i++) assert.ok(Math.abs(result.histogram[i]-(result.line[i]-result.signal[i]))<1e-10);
  const candles = values.map((close,i) => ({time:i*3600000,open:close,high:close+1,low:close-1,close,volume:10,closeTime:i*3600000+3599999}));
  const latest = charts.indicators(candles).macd_12_26;
  assert.ok(Number.isFinite(latest.line));
  assert.ok(Number.isFinite(latest.signal));
  assert.ok(Number.isFinite(latest.histogram));
});


test("chart load rejects non-object payloads and missing klines without replacing the prior chart", async () => {
  const host = { replaceChildren() {}, append() {} };
  const summary = { textContent: "" };
  const output = { textContent: "" };
  const state = { textContent: "" };
  const originalDocument = global.document;
  global.document = { getElementById(id) { return id === "chart-placeholder" ? host : id === "technical-summary" ? summary : id === "analysis-output" ? output : state; }, createElement() { return { setAttribute() {}, append() {}, appendChild() {}, style: {} }; }, createElementNS() { return { setAttribute() {}, append() {}, appendChild() {}, style: {} }; } };
  try {
    await assert.rejects(charts.load(async () => [], "SPOT", "BTCUSDT", "1h"), /invalid response shape/);
    await assert.rejects(charts.load(async () => ({ candles: [] }), "SPOT", "BTCUSDT", "1h"), /klines array/);
    assert.equal(output.textContent, "");
  } finally { global.document = originalDocument; }
});

test("chart load rejects unsupported selections before starting or superseding requests", async () => {
  let calls = 0;
  await assert.rejects(charts.load(async () => { calls++; return {}; }, "UNKNOWN", "BTCUSDT", "1h"), /Unsupported market type/);
  await assert.rejects(charts.load(async () => { calls++; return {}; }, "SPOT", "BTCUSDT", "2h30m"), /Unsupported chart timeframe/);
  await assert.rejects(charts.load(async () => { calls++; return {}; }, "SPOT", "   ", "1h"), /valid trading symbol/);
  assert.equal(calls, 0);
});

test("invalid chart selection does not supersede a valid request already in flight", async () => {
  let resolvePending;
  const pending = new Promise(resolve => { resolvePending = resolve; });
  const first = charts.load(() => pending, "SPOT", "BTCUSDT", "1h");
  await assert.rejects(charts.load(async () => ({}), "SPOT", "BTCUSDT", "2h30m"), /Unsupported chart timeframe/);
  resolvePending([]);
  await assert.rejects(first, /invalid response shape/);
});

test("a newer chart request supersedes an older response even when it fails", async () => {
  let resolveOlder;
  const older = new Promise(resolve => { resolveOlder = resolve; });
  const first = charts.load(() => older, "SPOT", "BTCUSDT", "1h");
  await assert.rejects(charts.load(async () => [], "SPOT", "ETHUSDT", "1h"), /invalid response shape/);
  resolveOlder([]);
  assert.deepEqual(await first, {status:"SUPERSEDED",market:"SPOT",symbol:"BTCUSDT",requested_timeframe:"1h"});
});

test("chart load rejects candle batches with no valid rows before rendering", async () => {
  const invalidRows = [[0, 10, 9, 8, 10, 1, 3599999], [3600000, null, 11, 9, 10, 1, 7199999]];
  await assert.rejects(charts.load(async () => ({klines:invalidRows}), "SPOT", "BTCUSDT", "1h"), /no valid complete candle rows; previous chart was preserved/);
});

test("latest RSI and ATR series values match the compact indicator snapshot", () => {
  const values = Array.from({length:80}, (_,i) => 120 + Math.sin(i/4)*3 + i*0.12);
  const candles = values.map((close,i) => ({time:i*3600000,open:close-0.15,high:close+1.1,low:close-0.9,close,volume:10,closeTime:i*3600000+3599999}));
  const snapshot = charts.indicators(candles);
  const rsi = charts.rsiSeries(values);
  const atr = charts.atrSeries(candles);
  assert.ok(Math.abs(rsi.at(-1)-snapshot.rsi_14_wilder)<1e-10);
  assert.ok(Math.abs(atr.at(-1)-snapshot.atr_14_wilder)<1e-10);
});

test("insufficient history leaves long-period indicators unavailable", () => {
  const rows = [candle(0, 100), candle(3600000, 101)];
  const result = charts.indicators(rows.map(row => ({time:row[0],open:row[1],high:row[2],low:row[3],close:row[4],volume:row[5],closeTime:row[6]})));
  assert.equal(result.ema_20, null);
  assert.equal(result.ema_200, null);
  assert.equal(result.rsi_14_wilder, null);
  assert.equal(result.atr_14_wilder, null);
});

test("Bollinger bands are candle-aligned and use population standard deviation", () => {
  const values = Array.from({length:25}, (_,i) => 100 + i);
  const bands = charts.bollingerSeries(values, 20, 2);
  assert.equal(bands.upper.length, values.length);
  assert.equal(bands.middle.slice(0,19).every(v => v === null), true);
  assert.equal(bands.lower.slice(0,19).every(v => v === null), true);
  assert.ok(bands.upper[19] > bands.middle[19]);
  assert.ok(bands.lower[19] < bands.middle[19]);
  assert.ok(Math.abs((bands.upper[19]+bands.lower[19])/2-bands.middle[19]) < 1e-10);
});

test("Wilder ADX and Stochastic RSI expose aligned bounded series with warm-up gaps", () => {
  const candles = Array.from({length:100}, (_,i) => {
    const close = 100 + i*0.4 + Math.sin(i/3);
    return {time:i*3600000,open:close-0.1,high:close+1,low:close-1,close,volume:10,closeTime:i*3600000+3599999};
  });
  const adx = charts.adxSeries(candles);
  const stoch = charts.stochRsiSeries(candles.map(x=>x.close));
  assert.equal(adx.length,candles.length);
  assert.equal(stoch.k.length,candles.length);
  assert.equal(stoch.d.length,candles.length);
  assert.equal(adx.slice(0,27).every(v=>v===null),true);
  assert.ok(Number.isFinite(adx[27]) && adx[27]>=0 && adx[27]<=100);
  assert.ok(adx.slice(27).every(v=>Number.isFinite(v)&&v>=0&&v<=100));
  assert.ok(stoch.k.slice(0,30).some(v=>v===null));
  assert.ok(stoch.k.filter(Number.isFinite).every(v=>v>=0&&v<=100));
  assert.ok(stoch.d.filter(Number.isFinite).every(v=>v>=0&&v<=100));
});

test("ADX reaches 100 on a steady one-directional trend after Wilder warm-up", () => {
  const candles = Array.from({length:80}, (_,i) => {
    const close = 100 + i;
    return {time:i*3600000,open:close-0.5,high:close+1,low:close-1,close,volume:1,closeTime:i*3600000+3599999};
  });
  const adx = charts.adxSeries(candles);
  assert.equal(adx.slice(0,27).every(value=>value===null),true);
  assert.ok(adx.slice(27).every(value=>Math.abs(value-100)<1e-10));
});

test("Stochastic RSI applies the documented K and D smoothing warm-up indices", () => {
  const values = Array.from({length:80}, (_,i) => 100 + Math.sin(i/3)*5 + i*0.1);
  const result = charts.stochRsiSeries(values,14,14,3,3);
  assert.equal(result.k.slice(0,29).every(value=>value===null),true);
  assert.equal(result.d.slice(0,31).every(value=>value===null),true);
  assert.ok(Number.isFinite(result.k[29]));
  assert.ok(Number.isFinite(result.d[31]));
});

test("Bollinger population deviation has a reproducible 20-candle reference value", () => {
  const values = Array.from({length:20}, (_,i) => i+1);
  const result = charts.bollingerSeries(values,20,2);
  const deviation = Math.sqrt(33.25);
  assert.ok(Math.abs(result.middle[19]-10.5)<1e-12);
  assert.ok(Math.abs(result.upper[19]-(10.5+2*deviation))<1e-12);
  assert.ok(Math.abs(result.lower[19]-(10.5-2*deviation))<1e-12);
});

test("flat candles produce neutral Stochastic RSI and zero ADX", () => {
  const candles = Array.from({length:80}, (_,i) => ({time:i*3600000,open:100,high:101,low:99,close:100,volume:1,closeTime:i*3600000+3599999}));
  const adx = charts.adxSeries(candles);
  const stoch = charts.stochRsiSeries(candles.map(x=>x.close));
  assert.ok(adx.slice(27).every(value => value === 0));
  assert.ok(stoch.k.slice(29).every(value => value === 50));
  assert.ok(stoch.d.slice(31).every(value => value === 50));
});

test("ADX and Stochastic RSI remain unavailable with insufficient history", () => {
  const candles = Array.from({length:20}, (_,i) => ({time:i,open:10,high:11,low:9,close:10,volume:1,closeTime:i+1}));
  assert.equal(charts.adxSeries(candles).every(v=>v===null),true);
  const stoch = charts.stochRsiSeries(candles.map(x=>x.close));
  assert.equal(stoch.k.every(v=>v===null),true);
  assert.equal(stoch.d.every(v=>v===null),true);
});
