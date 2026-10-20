import { describe, expect, it } from 'vitest';
import { DAY } from './macroChart.js';
import { historyFreshness, requireCurrentHistory } from './chartFreshness.js';

const day = Date.UTC(2026, 9, 20) / 1000;
const history = (end) => ({ captured_at: day, candles: [{ end, complete: true }], source: {} });
describe('chart candle freshness', () => {
  it('checks actual last candle rather than the claimed export cutoff', () => {
    const stale = historyFreshness(history(day - DAY), (day + 3600) * 1000);
    expect(stale.current).toBe(false);
    expect(stale.through_utc).toBe('2026-10-18');
    expect(stale.expected_through_utc).toBe('2026-10-19');
    expect(() => requireCurrentHistory(history(day - DAY), (day + 3600) * 1000)).toThrow(/not published/);
    expect(historyFreshness(history(day), (day + 3600) * 1000).current).toBe(true);
  });
  it('allows a five-minute midnight settlement margin and expires at the next expected close', () => {
    expect(historyFreshness(history(day - DAY), (day + 299) * 1000).current).toBe(true);
    expect(historyFreshness(history(day - DAY), (day + 300) * 1000).current).toBe(false);
    expect(historyFreshness(history(day), (day + DAY + 300) * 1000).current).toBe(false);
  });
  it('does not count open, future, or absent candles as current coverage', () => {
    expect(historyFreshness({ captured_at: day, candles: [{ end: day, complete: false }] }, (day + 3600) * 1000).current).toBe(false);
    expect(historyFreshness({ captured_at: day + DAY, candles: [{ end: day + DAY, complete: true }] }, (day + 3600) * 1000).current).toBe(false);
    expect(historyFreshness({ captured_at: day, candles: [] }, (day + 3600) * 1000).through_utc).toBe(null);
  });
});
