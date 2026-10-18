/** Read-only parity and prefix replay checks against explicitly selected exports. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { chartAt, confirmedPivots, defaultAnchors, fibScenario, parseHistory } from '../frontend/src/utils/macroChart.js';

const args = process.argv.slice(2);
assert.equal(args.length, 2, 'Usage: node scripts/verify_macro_chart.mjs DAILY.json WEEKLY.json');
const read = (path) => {
  const bytes = readFileSync(path);
  return { data: JSON.parse(bytes), sha256: createHash('sha256').update(bytes).digest('hex') };
};
const daily = read(args[0]);
const weekly = read(args[1]);
const history = parseHistory(daily.data);
assert.equal(weekly.data.contract, 'moonwalking.market-history/v1');
assert.equal(weekly.data.market.product_id, history.instrument.product_id);
assert.equal(weekly.data.market.venue, history.instrument.venue);
assert.equal(weekly.data.interval.seconds, 604800);
assert.equal(weekly.data.as_of, daily.data.as_of);
const chart = chartAt(history);
const expected = weekly.data.candles.filter((c) => c.complete && Date.parse(c.t) / 1000 + 604800 <= chart.as_of);
assert.equal(chart.candles.length, expected.length);
for (let i = 0; i < expected.length; i += 1) {
  const actual = chart.candles[i];
  const row = expected[i];
  assert.equal(actual.time, Date.parse(row.t) / 1000);
  for (const [field, key] of [['open', 'o'], ['high', 'h'], ['low', 'l'], ['close', 'c'], ['volume', 'v']]) {
    const tolerance = Math.max(1, Math.abs(row[key])) * 1e-12;
    assert.ok(Math.abs(actual[field] - row[key]) <= tolerance, `${i} ${field} differs`);
  }
}
let cutoffs = 0;
let scenarios = 0;
const fullPivots = confirmedPivots(chart.candles).pivots;
for (const candle of chart.candles) {
  const replay = chartAt(history, '1w', candle.end);
  const prefix = { ...history, candles: history.candles.filter((c) => c.end <= candle.end) };
  assert.deepEqual(replay.candles, chartAt(prefix, '1w', candle.end).candles);
  const pivots = confirmedPivots(replay.candles).pivots;
  assert.deepEqual(pivots, fullPivots.filter((p) => p.confirmed_at <= candle.end));
  const selected = defaultAnchors(pivots).map((id) => pivots.find((p) => p.id === id));
  const scenario = fibScenario(selected, replay.candles);
  if (!scenario.error) {
    assert.ok(scenario.available_at <= candle.end);
    scenarios += 1;
  }
  cutoffs += 1;
}
console.log(JSON.stringify({
  result: 'pass', instrument: history.instrument,
  daily_records: history.candles.length, complete_weekly_records: chart.candles.length,
  weekly_parity: 'OHLCV matches independently exported complete weeks within 1e-12 relative tolerance',
  replay_cutoffs_checked: cutoffs, cutoffs_with_valid_default_geometry: scenarios,
  confirmed_pivots: fullPivots.length, missing_days: chart.missing_days,
  daily_sha256: daily.sha256, weekly_sha256: weekly.sha256,
  limitation: 'Calculation and timing verification only; retrospective exports do not prove historical vendor availability or predictive edge.',
}, null, 2));
