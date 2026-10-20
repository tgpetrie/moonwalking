import test from 'node:test';
import assert from 'node:assert/strict';
import { DAY } from '../frontend/src/utils/macroChart.js';
import { compareReferenceScopes, runCli } from './chart_reference_comparison.mjs';

// Illustrative prices only; no market-performance claim.
const start = Date.UTC(2024, 0, 1) / 1000;
const candles = Array.from({ length: 500 }, (_, i) => {
  const close = 10 + Math.sin(i / 5);
  return { start: start + i * DAY, end: start + (i + 1) * DAY,
    open: close, close, high: close + 0.5, low: close - 0.5, volume: 100, complete: true };
});
const history = (rows) => ({ schema_version: 'bhabit.chart-history.v1',
  instrument: { product_id: 'EXAMPLE-USD', symbol: 'EXAMPLE', venue: 'illustrative', quote_currency: 'USD' },
  interval_seconds: DAY, captured_at: rows.at(-1).end, candles: rows });
const bytes = (value) => Buffer.from(JSON.stringify(value));

test('marks prices already spanned and keeps beyond-range observations distinct', () => {
  const rows = candles.map((p, i) => i === 499 ? { ...p, high: 15, low: 5 } : p);
  const result = compareReferenceScopes(bytes(history(rows)));
  assert.ok(result.daily_scopes[365].above.length);
  assert.ok(result.daily_scopes[365].above.every((p) => p.inside_latest_daily_range));
  assert.deepEqual(result.daily_scopes[365].outside_latest_range.above, []);
  assert.deepEqual(result.daily_scopes[365].outside_latest_range.below, []);
  assert.equal(result.daily_reference.high, 15);
});

test('replay excludes future prices from daily and weekly diagnostics', () => {
  const prefix = candles.slice(0, 421);
  const asOf = new Date((prefix.at(-1).end - DAY) * 1000).toISOString().slice(0, 10);
  const future = candles.map((p, i) => i > 420 ? { ...p, high: 9999, low: 0.1 } : p);
  const expected = compareReferenceScopes(bytes(history(prefix)), { asOf });
  const actual = compareReferenceScopes(bytes(history(future)), { asOf });
  const withoutSourceHash = ({ source, ...result }) => result;
  assert.deepEqual(withoutSourceHash(actual), withoutSourceHash(expected));
  assert.notEqual(actual.source.sha256, expected.source.sha256);
});

test('discloses daily/weekly baseline difference and does not backfill missing observations', () => {
  const result = compareReferenceScopes(bytes(history(candles.slice(0, 5))));
  assert.equal(result.weekly_reference, null);
  assert.deepEqual(result.weekly_nearby_references, { above: [], below: [] });
  assert.equal(result.settings.distances_use, 'latest completed daily close');
  assert.throws(() => runCli([]), /one or more/);
  assert.throws(() => runCli(['--forecast']), /Only --as-of/);
});
