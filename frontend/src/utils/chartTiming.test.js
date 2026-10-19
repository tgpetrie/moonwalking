import { describe, expect, it } from 'vitest';
import { DAY } from './macroChart.js';
import { historicalLegs, levelEpisodes } from './chartTiming.js';

// Illustrative prices and UTC dates only; these are not market observations.
const pivot = { time: 0, price: 100, confirmed_at: 2 * DAY };
const candle = (day, low = 90, high = 95, close = 92) => ({ time: day * DAY, end: (day + 1) * DAY, low, high, close });
const asOf = 13 * DAY;
const base = [candle(0, 99, 102, 100), candle(1), candle(2, 98, 101, 100), candle(3, 99, 103, 102),
  ...Array.from({ length: 9 }, (_, i) => candle(4 + i, 90, 95, i === 6 ? 94 : 92))];

describe('historical timing and level reactions', () => {
  it('measures dated extrema separately from later confirmation and withholds unavailable legs', () => {
    const anchors = [{ label: 'A', time: 0, extreme_time: DAY, price: 100, confirmed_at: 3 * DAY },
      { label: 'B', time: 10 * DAY, extreme_time: 12 * DAY, price: 50, confirmed_at: 14 * DAY }];
    expect(historicalLegs(anchors, 13 * DAY)).toEqual([]);
    expect(historicalLegs(anchors, 14 * DAY)[0]).toMatchObject({ label: 'A–B', start: DAY, end: 12 * DAY,
      days: 11, change_percent: -50, available_at: 14 * DAY, focus_start: DAY, focus_end: 12 * DAY });
    expect(historicalLegs(anchors, NaN)).toEqual([]);
  });
  it('starts after confirmation, joins only consecutive touch days and measures the exact seven-day close', () => {
    const result = levelEpisodes(base, pivot, { asOf });
    expect(result).toMatchObject({ lower: 99, upper: 101, missing_days: 0 });
    expect(result.episodes).toHaveLength(1);
    expect(result.episodes[0]).toMatchObject({ start: 2 * DAY, end: 4 * DAY, last_touch: 3 * DAY,
      touch_days: 2, approach: 'below', exit: 'below', exit_time: 4 * DAY, followup_at: 11 * DAY,
      followup_status: 'complete', next_day_close: 92 });
    expect(result.episodes[0].return_7d_percent).toBeCloseTo((94 / 102 - 1) * 100, 10);
  });
  it('does not merge visits across a non-touch day or missing interval', () => {
    const rows = [candle(2, 99, 101, 100), candle(3), candle(4, 99, 101, 100), candle(6, 99, 101, 100)];
    const result = levelEpisodes(rows, pivot, { asOf: 7 * DAY });
    expect(result.episodes.map((e) => e.touch_days)).toEqual([1, 1, 1]);
    expect(result.episodes[1].exit).toBe('gap');
    expect(result.missing_days).toBe(1);
  });
  it('reports incomplete and missing follow-ups instead of inventing returns', () => {
    const incomplete = levelEpisodes(base, pivot, { asOf: 6 * DAY }).episodes[0];
    expect(incomplete).toMatchObject({ followup_status: 'pending', return_7d_percent: null, followup_at: 11 * DAY });
    const missing = levelEpisodes(base.filter((r) => r.time !== 5 * DAY), pivot, { asOf }).episodes[0];
    expect(missing).toMatchObject({ followup_status: 'gap', return_7d_percent: null });
  });
  it('keeps the latest touching episode unresolved and reports no visits honestly', () => {
    const current = levelEpisodes([candle(2, 99, 101, 100)], pivot, { asOf: 3 * DAY });
    expect(current.episodes[0]).toMatchObject({ exit: 'pending', next_day_close: null, followup_status: 'pending' });
    expect(levelEpisodes([candle(2)], pivot, { asOf: 3 * DAY }).episodes).toEqual([]);
  });
  it('makes the inspection width explicit and includes exact boundary touches', () => {
    const rows = [candle(2, 101, 102, 101.5)];
    expect(levelEpisodes(rows, pivot, { asOf: 3 * DAY }).episodes).toHaveLength(1);
    expect(levelEpisodes(rows, pivot, { asOf: 3 * DAY, widthPercent: 0.5 }).episodes).toHaveLength(0);
    expect(levelEpisodes(rows, pivot, { asOf: 3 * DAY, widthPercent: 2 }).upper).toBe(102);
  });
  it('rejects unconfirmed levels, impossible input and duplicate daily buckets', () => {
    expect(levelEpisodes(base, pivot, { asOf: DAY })).toHaveProperty('error');
    expect(levelEpisodes(base, { ...pivot, confirmed_at: undefined }, { asOf })).toHaveProperty('error');
    expect(levelEpisodes(base, pivot, { asOf, widthPercent: 0 })).toHaveProperty('error');
    expect(levelEpisodes([candle(2), candle(2)], pivot, { asOf })).toHaveProperty('error');
    expect(levelEpisodes([{ ...candle(2), high: -1 }], pivot, { asOf })).toHaveProperty('error');
  });
  it('is identical on physically truncated input and ignores future price poisoning at every daily cutoff', () => {
    for (let day = 2; day <= 13; day += 1) {
      const cutoff = day * DAY;
      const expected = levelEpisodes(base.filter((c) => c.end <= cutoff), pivot, { asOf: cutoff });
      const poisoned = base.map((c) => c.end > cutoff ? { ...c, low: 1, high: 1000000, close: 1000 } : c);
      expect(levelEpisodes(base, pivot, { asOf: cutoff })).toEqual(expected);
      expect(levelEpisodes(poisoned, pivot, { asOf: cutoff })).toEqual(expected);
    }
  });
});
