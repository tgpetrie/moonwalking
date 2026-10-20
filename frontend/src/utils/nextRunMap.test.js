import { describe, expect, it } from 'vitest';
import { DAY, WEEK, aggregateWeeks } from './macroChart.js';
import { nextRunMap } from './nextRunMap.js';

// Illustrative synthetic prices only; not a market-performance fixture.
const start = Date.UTC(2024, 0, 1) / 1000;
const bars = Array.from({ length: 450 }, (_, i) => {
  const close = 10 + Math.sin(i / 3) * 2;
  return { time: start + i * DAY, end: start + (i + 1) * DAY,
    open: close, close, high: close + 0.2, low: close - 0.2 };
});
describe('next run reference scope', () => {
  it('keeps daily and complete weekly scopes separate, with honest candle-range context', () => {
    const daily = nextRunMap(bars, { asOf: bars.at(-1).end, lookbackDays: 90 });
    const weeks = aggregateWeeks(bars.map((p) => ({ ...p, complete: true })));
    const weekly = nextRunMap(weeks, { asOf: bars.at(-1).end, interval: WEEK });
    expect(daily.lookback_days).toBe(90);
    expect(weekly.interval_seconds).toBe(WEEK);
    expect(weekly.reference.complete).toBe(true);
    expect(weekly.reference.end).toBeLessThanOrEqual(daily.reference.end);
    expect(weekly.outside_range.above.every((p) => p.price > weekly.reference.high)).toBe(true);
    const poisoned = [...weeks, { ...weeks.at(-1), time: bars.at(-1).end, end: bars.at(-1).end + WEEK, high: 9999 }];
    expect(nextRunMap(poisoned, { asOf: bars.at(-1).end, interval: WEEK })).toEqual(weekly);
    expect([...daily.above, ...daily.below].every((p) => p.time >= daily.start)).toBe(true);
  });
  it('ranks actual confirmed highs/lows by distance and excludes old macro extremes', () => {
    const input = bars.map((b, i) => i === 20 ? { ...b, high: 10000 } : b);
    const map = nextRunMap(input, { asOf: bars.at(-1).end });
    expect(map.above.length).toBeGreaterThan(0);
    expect(map.below.length).toBeGreaterThan(0);
    expect(map.above.every((p) => p.price > map.reference.close && p.price < 100)).toBe(true);
    expect(map.below.every((p) => p.price < map.reference.close)).toBe(true);
    expect(map.above.map((p) => p.price)).toEqual(map.above.map((p) => p.price).sort((a, b) => a - b));
    expect(map.below.map((p) => p.price)).toEqual(map.below.map((p) => p.price).sort((a, b) => b - a));
    expect(map.above.map((p) => p.label)).toEqual(['H1', 'H2', 'H3'].slice(0, map.above.length));
    expect(map.below.map((p) => p.label)).toEqual(['L1', 'L2', 'L3'].slice(0, map.below.length));
    expect(map.above[0].display_label).toBe('Prior high 1');
    expect(map.below[0].display_label).toBe('Prior low 1');
    expect([...map.above, ...map.below].every((p) => p.time >= map.start && p.confirmed_at <= map.end)).toBe(true);
  });
  it('matches physical prefix replay even with poisoned future candles', () => {
    const asOf = bars[400].end;
    const expected = nextRunMap(bars.slice(0, 401), { asOf });
    const poisoned = bars.map((c) => c.end > asOf ? { ...c, high: 100000, close: 9999, low: 1 } : c);
    expect(nextRunMap(poisoned, { asOf })).toEqual(expected);
    expect([...expected.above, ...expected.below].every((p) => p.confirmed_at <= asOf)).toBe(true);
  });
  it('does not invent overhead references in price discovery or insufficient history', () => {
    const rising = bars.slice(0, 20).map((c, i) => ({ ...c, open: i + 1, close: i + 1, high: i + 1.1, low: i + 0.9 }));
    expect(nextRunMap(rising, { asOf: rising.at(-1).end }).above).toEqual([]);
    expect(nextRunMap([], { asOf: start }).reference).toBeNull();
  });
  it('cannot confirm across missing daily intervals', () => {
    const input = [10, 12, 10].map((value, i) => ({ time: start + i * 2 * DAY,
      end: start + (i * 2 + 1) * DAY, close: 10, high: value, low: value - 1 }));
    const map = nextRunMap(input, { asOf: input.at(-1).end, confirmation: 1 });
    expect(map.above).toEqual([]);
    expect(map.below).toEqual([]);
  });
});
