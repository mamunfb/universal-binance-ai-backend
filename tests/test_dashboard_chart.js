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

test("flat price RSI is neutral and ATR uses Wilder smoothing", () => {
  const flat = Array.from({length:16}, (_,i) => ({time:i*3600000,open:100,high:101,low:99,close:100,volume:1,closeTime:i*3600000+3599999}));
  const result = charts.indicators(flat);
  assert.equal(result.rsi_14_wilder, 50);
  assert.equal(result.atr_14_wilder, 2);
  assert.equal(result.candle_count, 16);
  assert.match(result.method, /not a validated trading signal/);
});

test("insufficient history leaves long-period indicators unavailable", () => {
  const rows = [candle(0, 100), candle(3600000, 101)];
  const result = charts.indicators(rows.map(row => ({time:row[0],open:row[1],high:row[2],low:row[3],close:row[4],volume:row[5],closeTime:row[6]})));
  assert.equal(result.ema_20, null);
  assert.equal(result.ema_200, null);
  assert.equal(result.rsi_14_wilder, null);
  assert.equal(result.atr_14_wilder, null);
});
