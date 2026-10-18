/** Replay a frozen video reference on a separately identified daily-price export.
 * No requests, database writes, parameter fitting, fills or profitability grades.
 * Usage: node scripts/replay_video_reference.mjs REFERENCE.json HISTORY.json
 */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { DAY, WEEK, chartAt, confirmedPivots, dateText, defaultAnchors, fibScenario, parseHistory } from '../frontend/src/utils/macroChart.js';

const [referencePath, historyPath, ...extra] = process.argv.slice(2);
assert.ok(referencePath && historyPath && !extra.length, 'Provide one reference and one history export');
const referenceBytes = readFileSync(referencePath);
const historyBytes = readFileSync(historyPath);
const reference = JSON.parse(referenceBytes);
const history = parseHistory(JSON.parse(historyBytes));
assert.equal(reference.schema_version, 'moonwalking.video-reference/v1');
assert.equal(reference.is_market_history, false);
assert.equal(history.instrument.symbol, reference.instrument.display_symbol);
assert.equal(history.instrument.quote_currency, reference.instrument.quote_currency);
const timestamp = (date) => Date.parse(`${date}T00:00:00Z`) / 1000;
const originalAt = timestamp(reference.original.published_on);
const updateAt = timestamp(reference.follow_up.published_on);
assert.ok(Number.isFinite(originalAt) && updateAt > originalAt, 'Dates must be chronological');
assert.ok(history.captured_at >= updateAt && history.candles[0].time < originalAt, 'History does not cover both dates');
const full = chartAt(history);
const allPivots = confirmedPivots(full.candles).pivots;
for (const row of full.candles) {
  const prefix = chartAt(history, '1w', row.end);
  assert.deepEqual(prefix.candles, full.candles.filter((c) => c.end <= row.end));
  assert.deepEqual(confirmedPivots(prefix.candles).pivots, allPivots.filter((p) => p.confirmed_at <= row.end));
}
const snapshots = [reference.original, reference.follow_up].map((source) => {
  // Explicit date-only UTC convention; the displayed upload date's timezone
  // and exact publication instant remain unverified. This is not exact PIT.
  const chart = chartAt(history, '1w', timestamp(source.published_on));
  const pivots = confirmedPivots(chart.candles).pivots;
  const anchors = defaultAnchors(pivots).map((id) => pivots.find((p) => p.id === id));
  const scenario = fibScenario(anchors, chart.candles);
  return {
    video_id: source.video_id, cutoff_exclusive: source.published_on,
    weekly_candles: chart.candles.length, last_completed_week: chart.candles.length ? dateText(chart.candles.at(-1).time) : null,
    last_completed_close: chart.candles.at(-1)?.close ?? null,
    anchors: anchors.map((p) => ({ type: p.type, date: dateText(p.extreme_time), price: p.price, confirmed_at: dateText(p.confirmed_at) })),
    scenario: scenario.error ? { state: 'withheld', reason: scenario.error } : {
      state: scenario.status, direction: scenario.direction, pullback_zone: scenario.pullback_zone, extension_zone: scenario.target_zone,
    },
  };
});
const start = originalAt + DAY;
const observed = history.candles.filter((c) => c.complete && c.time >= start && c.end <= updateAt);
const expected = (updateAt - start) / DAY;
const point = reference.original.level_claim.price;
assert.ok(Number.isFinite(point) && point > 0);
const touch = observed.find((c) => c.low <= point && c.high >= point);
const missing = expected - observed.length;
console.log(JSON.stringify({
  reference_id: reference.reference_id,
  reference_sha256: createHash('sha256').update(referenceBytes).digest('hex'),
  history_sha256: createHash('sha256').update(historyBytes).digest('hex'),
  source: history.instrument,
  provenance_note: 'Independent Coinbase proxy; matching the video CRYPTO feed, migration lineage and historical vendor availability are unverified.',
  timing_assumption: 'Upload calendar dates treated as UTC; exact publication time and displayed-date timezone are unverified.',
  settings: { interval_seconds: WEEK, left_confirmation: 2, right_confirmation: 2, anchors: 'latest alternating pivots; no search for favourable geometry' },
  complete_weekly_cutoffs_checked: full.candles.length, prefix_audit: 'pass', snapshots,
  point_touch_evaluation: {
    point, range_bounds: null, from_inclusive: dateText(start), until_exclusive: dateText(updateAt),
    observed_days: observed.length, missing_days: missing,
    minimum_observed_low: observed.length ? Math.min(...observed.map((c) => c.low)) : null,
    first_observed_touch_day: touch ? dateText(touch.time) : null,
    verdict: touch ? 'point touched in observed Coinbase daily range; no fill implied'
      : missing ? 'no observed touch; coverage incomplete' : 'point not touched in covered Coinbase daily ranges',
  },
  entry_fill: null, profitability_grade: null,
}, null, 2));
