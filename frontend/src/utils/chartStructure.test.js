import { describe, expect, it } from 'vitest';
import { DAY, chartAt, confirmedPivots, parseHistory } from './macroChart.js';
import { defaultMacroAnchors, macroRange, structurePivots, trendlineAt, trendlineSensitivity } from './chartStructure.js';
import { syntheticHistory } from '../test/macroHistory.test.fixture.js';

// All arithmetic fixtures in this file are illustrative, not market observations.
const anchors = [
  { time: 10 * DAY, price: 1, confirmed_at: 12 * DAY, wick_price: 1, body_price: 1.2 },
  { time: 20 * DAY, price: 4, confirmed_at: 22 * DAY, wick_price: 4, body_price: 4.4 },
];
const options = { asOf: 22 * DAY };

describe('macro drawdown range', () => {
  const high = { id: 'high', type: 'high', time: 10 * DAY, price: 20, confirmed_at: 12 * DAY };
  const low = { id: 'low', type: 'low', time: 20 * DAY, price: 10, confirmed_at: 22 * DAY };
  it('calculates linear-price levels independently of the chart display scale', () => {
    const result = macroRange(high, low, options);
    expect(result.error).toBeUndefined();
    expect(result.recovery_band[0]).toBe(15);
    expect(result.recovery_band[1]).toBeCloseTo(17.86, 12);
    for (const [ratio, price] of [[0, 10], [0.309, 13.09], [0.702, 17.02], [1, 20], [1.618, 26.18]]) {
      expect(result.levels.find((p) => p.ratio === ratio).price).toBeCloseTo(price, 12);
    }
    expect(result.available_at).toBe(low.confirmed_at);
    expect(result.interpretation).toMatch(/no forecast date or measured probability/);
  });
  it('chooses the highest confirmed high then the lowest subsequent low, without mutating input', () => {
    const before = { ...low, id: 'before', time: DAY, price: 1 };
    const later = { ...low, id: 'later', time: 30 * DAY, price: 11 };
    const input = [later, low, before, high];
    const original = [...input];
    expect(defaultMacroAnchors(input)).toEqual(['high', 'low']);
    expect(input).toEqual(original);
    expect(defaultMacroAnchors([before, high])).toEqual(['high', '']);
    expect(defaultMacroAnchors([before])).toEqual(['', '']);
    expect(defaultMacroAnchors([{ ...high, id: 'tie', time: 11 * DAY }, low, high])).toEqual(['high', 'low']);
    expect(defaultMacroAnchors([{ ...low, id: 'tie', time: 21 * DAY }, low, high])).toEqual(['high', 'low']);
  });
  it.each([
    ['missing anchor', undefined, low],
    ['wrong type', { ...high, type: 'low' }, low],
    ['earlier low', high, { ...low, time: high.time - DAY }],
    ['same time', high, { ...low, time: high.time }],
    ['higher low', high, { ...low, price: 21 }],
    ['nonpositive low', high, { ...low, price: 0 }],
    ['infinite high', { ...high, price: Infinity }, low],
    ['missing confirmation', high, { ...low, confirmed_at: undefined }],
    ['impossible confirmation', high, { ...low, confirmed_at: low.time - DAY }],
    ['future confirmation', high, { ...low, confirmed_at: 23 * DAY }],
  ])('withholds %s', (_, a, b) => {
    expect(macroRange(a, b, options)).toHaveProperty('error');
  });
  it('requires an explicit cutoff and rejects overflowing extension arithmetic', () => {
    expect(macroRange(high, low)).toHaveProperty('error');
    expect(macroRange({ ...high, price: Number.MAX_VALUE }, low, options).error).toMatch(/numeric limits/);
  });
  it('matches a physically truncated export at every replay cutoff', () => {
    const source = syntheticHistory();
    const parsed = parseHistory(source);
    for (const c of chartAt(parsed).candles) {
      const replay = chartAt(parsed, '1w', c.end);
      const truncated = chartAt(parseHistory({ ...source, captured_at: c.end,
        candles: source.candles.filter((row) => row.end <= c.end) }));
      const calculate = (chart) => {
        const pivots = confirmedPivots(chart.candles).pivots;
        const ids = defaultMacroAnchors(pivots);
        return macroRange(...ids.map((id) => pivots.find((p) => p.id === id)), { asOf: chart.as_of });
      };
      expect(calculate(replay)).toEqual(calculate(truncated));
      const result = calculate(replay);
      if (!result.error) expect(result.available_at).toBeLessThanOrEqual(c.end);
    }
  });
});

describe('trendline calculation and information timing', () => {
  it('passes through both anchor prices exactly within floating point tolerance', () => {
    for (const a of anchors) expect(trendlineAt(anchors, a.time, options).price).toBeCloseTo(a.price, 12);
  });
  it('uses a geometric midpoint on log scale and arithmetic midpoint on linear scale', () => {
    expect(trendlineAt(anchors, 15 * DAY, options).price).toBeCloseTo(2, 12);
    expect(trendlineAt(anchors, 15 * DAY, { ...options, scale: 'linear' }).price).toBe(2.5);
  });
  it('projects beyond the second anchor without pretending the price was observed', () => {
    const result = trendlineAt(anchors, 30 * DAY, options);
    expect(result.price).toBeCloseTo(16, 12);
    expect(result).toMatchObject({
      available_at: 22 * DAY, extrapolated: true, interpretation: 'hypothetical_projection',
    });
  });
  it('keeps historical fits labelled as references and carries their later availability', () => {
    expect(trendlineAt(anchors, 15 * DAY, options)).toMatchObject({
      interpretation: 'fitted_historical_reference', available_at: 22 * DAY, extrapolated: false,
    });
  });
  it('withholds an unconfirmed anchor rather than drawing it into earlier replay', () => {
    expect(() => trendlineAt(anchors, 30 * DAY, { asOf: 21 * DAY })).toThrow(/confirmed/);
    expect(() => trendlineAt(anchors.map(({ confirmed_at, ...a }) => a), 30 * DAY, options)).toThrow();
  });
  it.each([
    ['reversed times', [anchors[1], anchors[0]]],
    ['same timestamp', [anchors[0], { ...anchors[1], time: anchors[0].time }]],
    ['zero price', [anchors[0], { ...anchors[1], price: 0 }]],
    ['infinite price', [anchors[0], { ...anchors[1], price: Infinity }]],
  ])('rejects %s', (_, values) => {
    expect(() => trendlineAt(values, 30 * DAY, options)).toThrow();
  });
  it('rejects nonpositive linear projections and overflowing log projections', () => {
    const down = [anchors[1], { ...anchors[0], time: 30 * DAY, confirmed_at: 32 * DAY }];
    expect(() => trendlineAt(down, 50 * DAY, { asOf: 32 * DAY, scale: 'linear' })).toThrow(/positive/);
    expect(() => trendlineAt(anchors, 100000 * DAY, options)).toThrow(/finite/);
  });
  it('is invariant to translating both anchor and evaluation dates equally', () => {
    const shifted = anchors.map((p) => ({ ...p, time: p.time + 100 * DAY, confirmed_at: p.confirmed_at + 100 * DAY }));
    expect(trendlineAt(shifted, 130 * DAY, { asOf: 122 * DAY }).price).toBeCloseTo(trendlineAt(anchors, 30 * DAY, options).price, 12);
  });
  it('reports all four convention combinations as sensitivity, without invented thresholds', () => {
    const result = trendlineSensitivity(anchors, 30 * DAY, options);
    expect(result.variants).toHaveLength(4);
    expect(result.lower).toBeCloseTo(4 ** 2 / 1.2, 12);
    expect(result.upper).toBeCloseTo(4.4 ** 2, 12);
    expect(result.interpretation).toMatch(/not a statistical confidence interval/);
    expect(result).not.toHaveProperty('quality');
    expect(() => trendlineSensitivity([{ ...anchors[0], body_price: null }, anchors[1]], 30 * DAY, options)).toThrow();
  });
});

describe('wick and body pivot evidence', () => {
  const history = parseHistory(syntheticHistory());
  const candles = chartAt(history).candles;
  it('preserves the existing wick detector by default', () => {
    const result = structurePivots(candles);
    expect(result.pivots.map(({ price_basis, wick_price, body_price, ...p }) => p)).toEqual(confirmedPivots(candles).pivots);
    for (const p of result.pivots) expect(p.price).toBe(p.wick_price);
  });
  it('detects body extrema using candle bodies and retains their wick alternatives', () => {
    const result = structurePivots(candles, { mode: 'body' });
    expect(result.pivots.length).toBeGreaterThan(0);
    for (const p of result.pivots) {
      expect(p.price).toBe(p.body_price);
      expect(p.extreme_time).toBe(p.time);
      expect(p.type === 'high' ? p.wick_price >= p.body_price : p.wick_price <= p.body_price).toBe(true);
    }
    expect(() => structurePivots(candles, { mode: 'unknown' })).toThrow();
  });
  it.each(['wick', 'body'])('retains confirmed %s pivots across every later prefix', (mode) => {
    const full = structurePivots(candles, { mode }).pivots;
    for (const c of candles) {
      const prefix = candles.filter((row) => row.end <= c.end);
      expect(structurePivots(prefix, { mode }).pivots).toEqual(full.filter((p) => p.confirmed_at <= c.end));
    }
  });
});
