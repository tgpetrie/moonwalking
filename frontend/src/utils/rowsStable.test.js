import { describe, it, expect } from 'vitest';
import { rowsEqual, reconcileRows, trimList } from './rowsStable.js';

describe('rowsStable utilities', () => {
  it('rowsEqual compares core fields', () => {
    const a = { symbol: 'AAA', price: 1, change: 2, change3m: 3, peakCount: 0, rank: 1 };
    const b = { symbol: 'AAA', price: 1, change: 2, change3m: 3, peakCount: 0, rank: 1 };
    const c = { symbol: 'AAA', price: 2, change: 2, change3m: 3, peakCount: 0, rank: 1 };
    expect(rowsEqual(a, a)).toBe(true);
    expect(rowsEqual(a, b)).toBe(true);
    expect(rowsEqual(a, c)).toBe(false);
  });

  it('reconcileRows reuses identical objects', () => {
    const prev = [
      { symbol: 'A', price: 1, change: 0, change3m: 0, peakCount: 0, rank: 1 },
      { symbol: 'B', price: 2, change: 0, change3m: 0, peakCount: 0, rank: 2 }
    ];
    const nextRaw = [
      { symbol: 'A', price: 1, change: 0, change3m: 0, peakCount: 0, rank: 1 },
      { symbol: 'B', price: 3, change: 1, change3m: 0, peakCount: 0, rank: 2 }
    ];
    const reconciled = reconcileRows(nextRaw, prev);
    expect(reconciled[0]).toBe(prev[0]); // reused
    expect(reconciled[1]).not.toBe(prev[1]); // changed so new ref
    expect(reconciled[1].price).toBe(3);
  });

  it('trimList limits length', () => {
    const list = Array.from({ length: 100 }, (_, i) => i);
    const trimmed = trimList(list, 10);
    expect(trimmed.length).toBe(10);
    expect(trimmed[0]).toBe(0);
  });
});
