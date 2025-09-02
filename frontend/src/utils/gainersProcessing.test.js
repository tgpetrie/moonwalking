import { describe, it, expect } from 'vitest';
import { computeTop20Gainers, mockGainer } from './gainersProcessing.js';

describe('computeTop20Gainers', () => {
  it('returns previous slice if latestRaw empty', () => {
    const prev = [mockGainer('AAA', 5), mockGainer('BBB', 3)];
    const { combined } = computeTop20Gainers([], prev);
    expect(combined.length).toBe(2);
    expect(combined[0].symbol).toBe('AAA');
  });

  it('maps and ranks top items by change', () => {
    const raw = [
      { symbol: 'AAA-USD', peak_gain: 2 },
      { symbol: 'BBB-USD', peak_gain: 5 },
      { symbol: 'CCC-USD', peak_gain: 1 }
    ];
    const { combined } = computeTop20Gainers(raw, []);
    expect(combined[0].symbol).toBe('BBB');
    expect(combined[0].rank).toBe(1);
    expect(combined[1].rank).toBe(2);
  });

  it('merges previous positive movers not in latest', () => {
    const prev = [mockGainer('KEEP', 4), mockGainer('DROP', -1)];
    const raw = [ { symbol: 'NEW-USD', peak_gain: 6 } ];
    const { combined } = computeTop20Gainers(raw, prev, { limit: 5 });
    const symbols = combined.map(r => r.symbol);
    expect(symbols).toContain('KEEP');
    expect(symbols).toContain('NEW');
    expect(symbols).not.toContain('DROP');
  });

  it('can disable mergePrev', () => {
    const prev = [mockGainer('OLD', 10)];
    const raw = [ { symbol: 'NEW-USD', peak_gain: 1 } ];
    const { combined } = computeTop20Gainers(raw, prev, { mergePrev: false });
    expect(combined.some(r => r.symbol === 'OLD')).toBe(false);
    expect(combined[0].symbol).toBe('NEW');
  });
});