/** Adapted from verify_macro_chart.mjs: read-only macro-band replay audit. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { chartAt, confirmedPivots, parseHistory } from '../frontend/src/utils/macroChart.js';
import { defaultMacroAnchors, macroRange } from '../frontend/src/utils/chartStructure.js';

const paths = process.argv.slice(2);
assert.ok(paths.length, 'Usage: node scripts/verify_macro_range.mjs DAILY.json [DAILY.json ...]');
const select = (pivots, asOf) => macroRange(...defaultMacroAnchors(pivots)
  .map((id) => pivots.find((p) => p.id === id)), { asOf });
for (const path of paths) {
  const bytes = readFileSync(path);
  const history = parseHistory(JSON.parse(bytes));
  const chart = chartAt(history);
  const fullPivots = confirmedPivots(chart.candles).pivots;
  let valid = 0;
  for (const candle of chart.candles) {
    const replay = chartAt(history, '1w', candle.end);
    const prefix = chartAt({ ...history, captured_at: candle.end,
      candles: history.candles.filter((row) => row.end <= candle.end) }, '1w', candle.end);
    const pivots = confirmedPivots(replay.candles).pivots;
    const result = select(pivots, candle.end);
    assert.deepEqual(result, select(confirmedPivots(prefix.candles).pivots, candle.end));
    assert.deepEqual(result, select(fullPivots.filter((p) => p.confirmed_at <= candle.end), candle.end));
    if (!result.error) {
      assert.ok(result.available_at <= candle.end);
      assert.ok(result.anchors.every((p) => p.confirmed_at <= candle.end));
      valid += 1;
    }
  }
  const final = select(fullPivots, chart.as_of);
  console.log(JSON.stringify({ product_id: history.instrument.product_id,
    input_sha256: createHash('sha256').update(bytes).digest('hex'),
    weekly_cutoffs_checked: chart.candles.length, cutoffs_with_macro_range: valid,
    final_range: final, result: 'pass',
    limitation: 'Bar-based information timing and arithmetic only. No predictive or historical vendor-availability claim.' }, null, 2));
}
