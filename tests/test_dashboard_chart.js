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
    {time:1,open:10,high:12,low:9,close:12,volume:Number.MAX_VALUE,closeTime:2},
    {time:3,open:22,high:24,low:21,close:24,volume:Number.MAX_VALUE,closeTime:4}
  ];
  const result = charts.indicators(candles);
  assert.equal(result.vwap, 17);
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

test("indicator averages remain finite for large but finite OHLCV values", () => {
  const close = Number.MAX_VALUE * 0.75;
  const candles = Array.from({length:40}, (_,i) => ({
    time:i*3600000,open:close,high:Number.MAX_VALUE*0.8,low:Number.MAX_VALUE*0.7,
    close,volume:Number.MAX_VALUE,closeTime:i*3600000+3599999
  }));
  const ema = charts.emaSeries(candles.map(x=>x.close),20);
  const rsi = charts.rsiSeries(candles.map(x=>x.close));
  const atr = charts.atrSeries(candles);
  const bands = charts.bollingerSeries(candles.map(x=>x.close),20,2);
  assert.ok(Number.isFinite(ema.at(-1)));
  assert.equal(rsi.at(-1),50);
  assert.ok(Number.isFinite(atr.at(-1)));
  assert.ok(Number.isFinite(bands.middle.at(-1)));
  assert.ok(Number.isFinite(bands.upper.at(-1)));
  assert.ok(Number.isFinite(bands.lower.at(-1)));
  const snapshot = charts.indicators(candles);
  assert.ok(Number.isFinite(snapshot.vwap));
  assert.ok(Number.isFinite(snapshot.atr_14_wilder));
});

test("Bollinger bands leave unrepresentable extreme bounds unavailable instead of Infinity", () => {
  const values = Array.from({length:20}, (_,i) => i%2 ? Number.MAX_VALUE : -Number.MAX_VALUE);
  const bands = charts.bollingerSeries(values,20,2);
  assert.equal(bands.middle[19],0);
  assert.equal(bands.upper[19],null);
  assert.equal(bands.lower[19],null);
});

test("ADX remains finite when directional-movement accumulators would overflow", () => {
  const step = Number.MAX_VALUE * 0.005;
  const range = Number.MAX_VALUE * 0.1;
  const candles = Array.from({length:80}, (_,i) => {
    const high = Number.MAX_VALUE * 0.5 + i * step;
    const low = high - range;
    const close = low + range / 2;
    return {time:i*3600000,open:close,high,low,close,volume:1,closeTime:i*3600000+3599999};
  });
  const adx = charts.adxSeries(candles);
  assert.ok(adx.slice(27).every(Number.isFinite));
  assert.ok(adx.slice(27).every(value => Math.abs(value-100)<1e-10));
});

test("chart rendering handles signed indicator ranges and normalized zero baselines", async () => {
  const host = { replaceChildren() {}, append() {} };
  const summary = { textContent: "" };
  const output = { textContent: "" };
  const state = { textContent: "" };
  const originalDocument = global.document;
  const element = () => ({ setAttribute() {}, append() {}, appendChild() {}, style: {} });
  global.document = {
    getElementById(id) { return id === "chart-placeholder" ? host : id === "technical-summary" ? summary : id === "analysis-output" ? output : state; },
    createElement: element,
    createElementNS: element
  };
  const rows = Array.from({length:80}, (_,i) => {
    const close = 100 + Math.sin(i/3)*10;
    return [i*3600000,close,close+1,close-1,close,10,i*3600000+3599999];
  });
  try {
    const result = await charts.load(async () => ({klines:rows}), "SPOT", "BTCUSDT", "1h");
    assert.equal(result.candle_count,80);
    assert.ok(output.textContent.includes("macd_12_26"));
  } finally { global.document = originalDocument; }
});

test("MACD series never exposes non-finite histogram values for extreme finite prices", () => {
  const values = Array.from({length:160}, (_,i) => i%2 ? Number.MAX_VALUE*0.9 : Number.MAX_VALUE*0.01);
  const result = charts.macdComponents(values);
  for (const series of [result.line,result.signal,result.histogram]) {
    assert.ok(series.every(value => value === null || Number.isFinite(value)));
  }
});

test("Stochastic RSI safely rejects non-array input", () => {
  assert.deepEqual(charts.stochRsiSeries(null),{k:[],d:[]});
  assert.deepEqual(charts.stochRsiSeries({}),{k:[],d:[]});
});

test("Stochastic RSI rejects invalid periods without producing non-finite values", () => {
  const values = Array.from({length:80}, (_,i) => 100+i);
  for (const params of [[0,14,3,3],[14,0,3,3],[14,14,0,3],[14,14,3,0],[1.5,14,3,3],[Number.MAX_SAFE_INTEGER,2,3,3]]) {
    const result = charts.stochRsiSeries(values,...params);
    assert.ok(result.k.every(value => value === null || Number.isFinite(value)));
    assert.ok(result.d.every(value => value === null || Number.isFinite(value)));
    assert.equal(result.k.every(value => value === null),true);
    assert.equal(result.d.every(value => value === null),true);
  }
});

test("indicator series reject invalid containers and period arguments safely", () => {
  assert.deepEqual(charts.emaSeries(null,14),[]);
  assert.deepEqual(charts.rsiSeries(null,14),[]);
  assert.deepEqual(charts.atrSeries(null,14),[]);
  assert.deepEqual(charts.adxSeries(null,14),[]);
  const values = Array.from({length:40}, (_,i) => 100+i);
  const candles = values.map((close,i) => ({time:i,open:close,high:close+1,low:close-1,close,volume:1,closeTime:i+1}));
  for (const invalid of [0,-1,1.5,Number.MAX_SAFE_INTEGER+1]) {
    assert.ok(charts.emaSeries(values,invalid).every(value => value===null));
    assert.ok(charts.rsiSeries(values,invalid).every(value => value===null));
    assert.ok(charts.atrSeries(candles,invalid).every(value => value===null));
    assert.ok(charts.adxSeries(candles,invalid).every(value => value===null));
  }
});

test("3h aggregation rejects invalid containers and malformed candle objects", () => {
  assert.deepEqual(charts.aggregate3h(null),[]);
  assert.deepEqual(charts.aggregate3h([null,{}, {time:0}]),[]);
  const valid = Array.from({length:3}, (_,i) => ({time:i*3600000,open:10,high:12,low:9,close:11,volume:1,closeTime:i*3600000+3599999}));
  assert.equal(charts.aggregate3h(valid).length,1);
  const malformed = valid.map(x=>({...x}));
  malformed[1].volume = Number.POSITIVE_INFINITY;
  assert.deepEqual(charts.aggregate3h(malformed),[]);
});

test("candle parsing accepts decimal numeric strings but rejects non-decimal coercions", () => {
  const decimal = ["1000","10.5","12","9","11","0.25","3600999"];
  const parsed = charts.parse([decimal]);
  assert.equal(parsed.length,1);
  assert.equal(parsed[0].open,10.5);
  for (const invalid of ["0x10","0b10","0o10"," ","Infinity",true]) {
    const row = [0,10,11,9,10,1,3599999];
    row[1] = invalid;
    assert.deepEqual(charts.parse([row]),[]);
  }
});

test("candle parsing discards every row sharing a duplicate open timestamp", () => {
  const duplicateA = candle(0,100);
  const duplicateB = candle(0,101);
  const unique = candle(3600000,102);
  const parsed = charts.parse([duplicateA,unique,duplicateB]);
  assert.deepEqual(parsed.map(row=>row.time),[3600000]);
});

test("EMA, RSI and ATR series resume after finite-data gaps with fresh warmup windows", () => {
  const ema = charts.emaSeries([1,2,3,4,NaN,10,11,12,13],3);
  assert.equal(ema[2],2);
  assert.equal(ema[4],null);
  assert.equal(ema[6],null);
  assert.equal(ema[7],11);
  assert.ok(Number.isFinite(ema[8]));

  const rsi = charts.rsiSeries([10,11,12,NaN,20,19,18,17],2);
  assert.equal(rsi[2],100);
  assert.equal(rsi[3],null);
  assert.equal(rsi[5],null);
  assert.equal(rsi[6],0);
  assert.equal(rsi[7],0);

  const candles = Array.from({length:7}, (_,i) => ({
    time:i,open:10,high:12,low:9,close:11,volume:1,closeTime:i+1
  }));
  candles[3].close = NaN;
  const atr = charts.atrSeries(candles,2);
  assert.ok(Number.isFinite(atr[2]));
  assert.equal(atr[3],null);
  assert.equal(atr[4],null);
  assert.equal(atr[5],null);
  assert.ok(Number.isFinite(atr[6]));
});

test("ADX restarts after invalid candle gaps without carrying directional state across them", () => {
  const candles = Array.from({length:90}, (_,i) => {
    const close = 100+i;
    return {time:i,open:close,high:close+1,low:close-1,close,volume:1,closeTime:i+1};
  });
  candles[40].high = NaN;
  const adx = charts.adxSeries(candles,14);
  assert.ok(Number.isFinite(adx[39]));
  assert.equal(adx[40],null);
  assert.equal(adx[67],null);
  assert.ok(Number.isFinite(adx[68]));
  assert.ok(Math.abs(adx[68]-100)<1e-10);
});

test("Bollinger and MACD series retain candle alignment and restart after gaps", () => {
  const values = Array.from({length:110}, (_,i) => 100 + Math.sin(i/4)*5 + i*0.1);
  values[50] = NaN;
  const bands = charts.bollingerSeries(values,20,2);
  assert.equal(bands.middle[50],null);
  assert.equal(bands.middle[68],null);
  assert.ok(Number.isFinite(bands.middle[69]));

  const macd = charts.macdComponents(values);
  assert.equal(macd.line[50],null);
  assert.equal(macd.signal[50],null);
  assert.ok(Number.isFinite(macd.line[75]));
  assert.equal(macd.signal[75],null);
  assert.ok(Number.isFinite(macd.signal[83]));
  assert.equal(macd.histogram.length,values.length);
  assert.ok(macd.histogram.every(value=>value===null||Number.isFinite(value)));
});

test("volume bars scale tiny positive volumes correctly and keep all-zero volume finite", async () => {
  const makeElement = tag => ({
    tagName:tag,attributes:{},children:[],style:{},textContent:"",
    setAttribute(key,value){this.attributes[key]=String(value);},
    append(...nodes){this.children.push(...nodes);},
    replaceChildren(...nodes){this.children=[...nodes];}
  });
  const host = makeElement("host");
  const nodes = {"chart-placeholder":host,"technical-summary":makeElement("summary"),"analysis-output":makeElement("output"),"chart-state":makeElement("state")};
  const originalDocument = global.document;
  global.document = {
    getElementById(id){return nodes[id];},
    createElement(tag){return makeElement(tag);},
    createElementNS(_ns,tag){return makeElement(tag);}
  };
  const rows = Array.from({length:80}, (_,i) => {
    const close=100+i*0.1, volume=i===0?1e-300:i===1?5e-300:0;
    return [i*3600000,close,close+1,close-1,close,volume,i*3600000+3599999];
  });
  try {
    await charts.load(async()=>({klines:rows}),"SPOT","BTCUSDT","1h");
    const bars=host.children[0].children.filter(node=>node.tagName==="rect"&&node.attributes.opacity==="0.4");
    assert.equal(Number(bars[0].attributes.height),10);
    assert.equal(Number(bars[1].attributes.height),50);
    const zeroRows=rows.map(row=>[...row.slice(0,5),0,row[6]]);
    await charts.load(async()=>({klines:zeroRows}),"SPOT","BTCUSDT","1h");
    const zeroBars=host.children[0].children.filter(node=>node.tagName==="rect"&&node.attributes.opacity==="0.4");
    assert.ok(zeroBars.every(node=>Number(node.attributes.height)===0));
    assert.ok(zeroBars.every(node=>Object.values(node.attributes).every(value=>!/(?:NaN|Infinity)/.test(value))));
  } finally { global.document=originalDocument; }
});

test("chart invalidation actively aborts the in-flight API request and ignores its response", async () => {
  let resolvePending, receivedSignal;
  const pending = new Promise(resolve => { resolvePending=resolve; });
  const request = charts.load((_url,options={}) => { receivedSignal=options.signal; return pending; },"SPOT","BTCUSDT","1h");
  assert.ok(receivedSignal);
  assert.equal(receivedSignal.aborted,false);
  charts.invalidate();
  assert.equal(receivedSignal.aborted,true);
  resolvePending({klines:[]});
  assert.deepEqual(await request,{status:"SUPERSEDED",market:"SPOT",symbol:"BTCUSDT",requested_timeframe:"1h"});
});

test("chart load bounds oversized backend candle payloads to the latest 1000 source rows", async () => {
  const makeElement = tag => ({
    tagName:tag,attributes:{},children:[],style:{},textContent:"",
    setAttribute(key,value){this.attributes[key]=String(value);},
    append(...nodes){this.children.push(...nodes);},
    replaceChildren(...nodes){this.children=[...nodes];}
  });
  const nodes = {"chart-placeholder":makeElement("host"),"technical-summary":makeElement("summary"),"analysis-output":makeElement("output"),"chart-state":makeElement("state")};
  const originalDocument=global.document;
  global.document={getElementById(id){return nodes[id];},createElement:makeElement,createElementNS(_ns,tag){return makeElement(tag);}};
  const rows=Array.from({length:1200},(_,i)=>{const close=100+i/10;return [i*3600000,close,close+1,close-1,close,1,i*3600000+3599999];});
  try {
    const result=await charts.load(async()=>({klines:rows}),"SPOT","BTCUSDT","1h");
    assert.equal(result.source_rows_received,1200);
    assert.equal(result.source_rows_processed,1000);
    assert.equal(result.candle_count,1000);
    assert.equal(result.latest_candle_time_utc,new Date(rows.at(-1)[0]).toISOString());
  } finally {global.document=originalDocument;}
});

test("Stochastic RSI rolling extrema and smoothing restart cleanly after missing observations", () => {
  const values=Array.from({length:100},(_,i)=>100+Math.sin(i/3)*6+i*0.08);
  values[52]=NaN;
  const result=charts.stochRsiSeries(values,14,14,3,3);
  assert.equal(result.k[52],null);
  assert.equal(result.d[52],null);
  assert.equal(result.k[81],null);
  assert.equal(result.d[83],null);
  assert.ok(Number.isFinite(result.k[82]));
  assert.ok(Number.isFinite(result.d[84]));
  assert.ok(result.k.every(value=>value===null||(Number.isFinite(value)&&value>=0&&value<=100)));
  assert.ok(result.d.every(value=>value===null||(Number.isFinite(value)&&value>=0&&value<=100)));
});

test("optimized Stochastic RSI matches a straightforward rolling-window reference", () => {
  const values=Array.from({length:140},(_,i)=>90+Math.sin(i/5)*8+Math.cos(i/11)*3+i*0.04);
  const rsi=charts.rsiSeries(values,10),raw=Array(values.length).fill(null),expectedK=Array(values.length).fill(null),expectedD=Array(values.length).fill(null);
  for(let i=0;i<rsi.length;i++){
    if(i<10+12-1||!Number.isFinite(rsi[i]))continue;
    const window=rsi.slice(i-11,i+1);if(!window.every(Number.isFinite))continue;
    const lo=Math.min(...window),hi=Math.max(...window);raw[i]=hi===lo?50:(rsi[i]-lo)/(hi-lo)*100;
  }
  for(let i=0;i<raw.length;i++){
    if(i>=2&&raw.slice(i-2,i+1).every(Number.isFinite))expectedK[i]=raw.slice(i-2,i+1).reduce((sum,value)=>sum+value,0)/3;
    if(i>=4&&expectedK.slice(i-2,i+1).every(Number.isFinite))expectedD[i]=expectedK.slice(i-2,i+1).reduce((sum,value)=>sum+value,0)/3;
  }
  const actual=charts.stochRsiSeries(values,10,12,3,3);
  for(let i=0;i<values.length;i++){
    if(expectedK[i]===null)assert.equal(actual.k[i],null);else assert.ok(Math.abs(actual.k[i]-expectedK[i])<1e-10);
    if(expectedD[i]===null)assert.equal(actual.d[i],null);else assert.ok(Math.abs(actual.d[i]-expectedD[i])<1e-10);
  }
});

test("ADX treats structurally invalid OHLC bounds as a segment break and fully warms up again", () => {
  const candles=Array.from({length:100},(_,i)=>{
    const close=100+i;
    return {time:i,open:close,high:close+1,low:close-1,close,volume:1,closeTime:i+1};
  });
  candles[45].high=candles[45].close-0.5;
  const adx=charts.adxSeries(candles,14);
  assert.ok(Number.isFinite(adx[40]));
  assert.equal(adx[45],null);
  assert.equal(adx[72],null);
  assert.ok(Number.isFinite(adx[73]));
  assert.ok(Math.abs(adx[73]-100)<1e-10);
});

test("ATR rejects malformed current and previous OHLC candles and restarts its Wilder warm-up", () => {
  const candles=Array.from({length:100},(_,i)=>{
    const close=100+i;
    return {time:i,open:close,high:close+1,low:close-1,close,volume:1,closeTime:i+1};
  });
  candles[45].high=candles[45].close-0.5;
  const atr=charts.atrSeries(candles,14);
  assert.ok(Number.isFinite(atr[44]));
  assert.equal(atr[45],null);
  assert.equal(atr[46],null);
  assert.equal(atr[59],null);
  assert.ok(Number.isFinite(atr[60]));
});

test("Wilder RSI and ATR smoothing remain finite for very large representable gains and ranges", () => {
  const step=Number.MAX_VALUE*0.003;
  const range=Number.MAX_VALUE*0.01;
  const closes=Array.from({length:80},(_,i)=>Number.MAX_VALUE*0.5+step*i);
  const candles=closes.map((close,i)=>({
    time:i*3600000,open:close,high:close+range,low:close-range,
    close,volume:1,closeTime:i*3600000+3599999
  }));
  const rsi=charts.rsiSeries(closes,14);
  const atr=charts.atrSeries(candles,14);
  assert.equal(rsi.at(-1),100);
  assert.ok(Number.isFinite(atr.at(-1)));
  assert.equal(charts.rsi(closes,14),100);
  assert.ok(Number.isFinite(charts.atrWilder(candles,14)));
});

