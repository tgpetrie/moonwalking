/** Adapted from verify_macro_range.mjs: read-only daily reaction timing audit. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { chartAt, confirmedPivots, parseHistory } from '../frontend/src/utils/macroChart.js';
import { historicalLegs, levelEpisodes } from '../frontend/src/utils/chartTiming.js';
import { recentSwingSequence } from '../frontend/src/utils/chartStructure.js';

const paths = process.argv.slice(2);
assert.ok(paths.length, 'Usage: node scripts/verify_chart_timing.mjs DAILY.json [DAILY.json ...]');
for (const path of paths) {
  const bytes = readFileSync(path);
  const history = parseHistory(JSON.parse(bytes));
  const weekly = chartAt(history);
  const fullDaily = chartAt(history, '1d').candles;
  let checks = 0;
  let episodes = 0;
  for (const candle of weekly.candles) {
    const asOf = candle.end;
    const pivots = confirmedPivots(chartAt(history, '1w', asOf).candles).pivots;
    const prefix = fullDaily.filter((row) => row.end <= asOf);
    const poisoned = fullDaily.map((row) => row.end > asOf ? { ...row, low: 0.001, high: 1000000, close: 500000 } : row);
    for (const type of ['low', 'high']) {
      const pivot = pivots.filter((p) => p.type === type).at(-1);
      if (!pivot) continue;
      const actual = levelEpisodes(fullDaily, pivot, { asOf });
      assert.deepEqual(actual, levelEpisodes(prefix, pivot, { asOf }));
      assert.deepEqual(actual, levelEpisodes(poisoned, pivot, { asOf }));
      assert.ok(!actual.error);
      for (const event of actual.episodes) {
        assert.ok(event.start >= pivot.confirmed_at && event.end <= asOf);
        if (event.followup_status === 'complete') assert.ok(event.followup_at <= asOf);
        else assert.equal(event.return_7d_percent, null);
      }
      checks += 1; episodes += actual.episodes.length;
    }
    const legs = historicalLegs(recentSwingSequence(pivots, { asOf }), asOf);
    assert.ok(legs.every((leg) => leg.available_at <= asOf && leg.end < asOf));
  }
  console.log(JSON.stringify({ product_id: history.instrument.product_id,
    sha256: createHash('sha256').update(bytes).digest('hex'), weekly_cutoffs: weekly.candles.length,
    level_checks: checks, episode_records_checked: episodes, result: 'pass',
    limitation: 'Records recur across overlapping replay cutoffs; these are audit counts, not independent trades or forecast evidence.' }, null, 2));
}
