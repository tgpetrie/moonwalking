import { describe, it, expect } from 'vitest';
import { normalizeBannerRow, normalizeTableRow } from '../adapters';

describe('adapters.normalizeBannerRow', () => {
  it('extracts canonical fields from common shapes', () => {
    const raw = {
      symbol: 'edge-usd',
      current_price: 0.26142,
      price_change_1h: 0.5,
      volume_1h: 1234567,
      volume_change_1h_pct: 12.34,
    } as any;
    const out = normalizeBannerRow(raw);
    expect(out.symbol).toBe('EDGE-USD');
    expect(out.currentPrice).toBeCloseTo(0.26142, 6);
    expect(out.priceChange1h).toBeCloseTo(0.5, 6);
    expect(out.volumeNow).toBe(1234567);
    expect(out.volumeChangePct).toBeCloseTo(12.34, 6);
    expect(out.volumeChangeIsEstimated).toBe(false);
  });

  it('does not infer volume movement from price movement', () => {
    const out = normalizeBannerRow({
      symbol: 'BTC-USD',
      price_change_1h: 4.2,
      volume_change_estimate: 2.1,
      volume_change_is_estimated: true,
    } as any);

    expect(out.priceChange1h).toBe(4.2);
    expect(out.volumeChangePct).toBeNull();
    expect(out.volumeChangeIsEstimated).toBe(true);
  });
});

describe('adapters.normalizeTableRow', () => {
  it('includes rank and trend fields when present', () => {
    const raw = { symbol: 'BTC-USD', rank: 1, trend_direction: 'up', trend_score: 0.12 } as any;
    const out = normalizeTableRow(raw);
    expect(out.symbol).toBe('BTC-USD');
    expect(out.rank).toBe(1);
    expect(out.trendDirection).toBe('up');
    expect(out.trendScore).toBe(0.12);
  });
});
