import { describe, expect, it } from 'vitest';
import { syntheticHistory, syntheticMarketHistory } from '../test/macroHistory.test.fixture.js';
import { DAY, WEEK, aggregateWeeks, chartAt, confirmedPivots, defaultAnchors, fibScenario, mondayStart, parseHistory, priceScale, priceText } from './macroChart.js';

describe('price display transforms', () => {
  it('spaces equal price ratios equally on the logarithmic canvas', () => {
    const axis = priceScale([1, 2, 4, 8], 'log');
    expect(axis.position(2) - axis.position(1)).toBeCloseTo(axis.position(8) - axis.position(4), 12);
    expect(axis.ticks.every((tick) => tick > 0)).toBe(true);
  });
  it('spaces equal price differences equally on the linear canvas', () => {
    const axis = priceScale([1, 2, 4, 8], 'linear');
    expect(axis.position(2) - axis.position(1)).toBeCloseTo(axis.position(4) - axis.position(3), 12);
  });
  it('handles a constant positive price without zero-width domains', () => {
    expect(Number.isFinite(priceScale([1, 1], 'log').position(1))).toBe(true);
    expect(() => priceScale([0, 1], 'log')).toThrow();
    expect(() => priceScale([1], 'unknown')).toThrow();
  });
});

describe('macro chart data and information timing', () => {
  it('adapts Claude’s unstitched market-history contract and preserves provenance', () => {
    const input = syntheticMarketHistory();
    const result = parseHistory(input);
    expect(result.candles).toEqual(parseHistory(syntheticHistory()).candles);
    expect(result.source.series_id).toBe('test-venue:TEST-USD:1d');
    expect(result.source.provenance.stitched).toBe(false);
  });

  it.each([
    ['stitched series', (input) => { input.provenance.stitched = true; }],
    ['ambiguous timezone', (input) => { input.as_of = input.as_of.replace('Z', ''); }],
    ['nonexistent date', (input) => { input.candles[0].t = '2024-02-31T00:00:00Z'; }],
    ['quote conversion', (input) => { input.market.price_unit = 'USDT'; }],
    ['incorrect volume units', (input) => { input.market.volume_unit = 'USD'; }],
    ['preaggregated weekly input', (input) => { input.interval.granularity = '1w'; }],
  ])('rejects market history with %s', (_, mutate) => {
    const input = syntheticMarketHistory(); mutate(input);
    expect(() => parseHistory(input)).toThrow();
  });

  it('normalizes a dated instrument history without inventing rows', () => {
    const input = syntheticHistory();
    input.candles.reverse();
    const parsed = parseHistory(input);
    expect(parsed.candles).toHaveLength(210);
    expect(parsed.candles[0].time).toBe(Date.UTC(2024, 0, 1) / 1000);
    expect(parsed.instrument.venue).toBe('Synthetic test fixture');
  });

  it.each([
    ['duplicate timestamps', (data) => data.candles.push(data.candles[0])],
    ['non-numeric close', (data) => { data.candles[0].close = null; }],
    ['inconsistent OHLC', (data) => { data.candles[0].high = 1; }],
    ['non-finite price', (data) => { data.candles[0].low = Infinity; }],
    ['unclosed complete candle', (data) => { data.captured_at = data.candles.at(-1).end - 1; }],
    ['missing venue', (data) => { data.instrument.venue = ''; }],
    ['wrong interval', (data) => { data.interval_seconds = 3600; }],
    ['non-midnight daily candle', (data) => { data.candles[0].start += 1; }],
  ])('rejects %s', (_, mutate) => {
    const input = syntheticHistory(); mutate(input);
    expect(() => parseHistory(input)).toThrow();
  });

  it('aggregates full UTC Monday weeks using actual OHLC and volume', () => {
    const history = parseHistory(syntheticHistory());
    const weekly = aggregateWeeks(history.candles);
    expect(weekly).toHaveLength(30);
    expect(weekly[0]).toMatchObject({ time: history.candles[0].time, open: 11.9, close: 12.06, day_count: 7, complete: true, volume: 721 });
    expect(weekly[0].high).toBeCloseTo(12.46);
    expect(weekly[0].low).toBeCloseTo(11.6);
    expect(mondayStart(history.candles[3].time)).toBe(history.candles[0].time);
  });

  it('excludes missing-day weeks and counts the gap rather than filling it', () => {
    const input = syntheticHistory(); input.candles.splice(10, 1);
    const chart = chartAt(parseHistory(input));
    expect(chart.missing_days).toBe(1);
    expect(chart.excluded_weeks).toBe(1);
    expect(chart.candles).toHaveLength(29);
  });

  it('keeps incomplete candles excluded even when the wall clock advances', () => {
    const input = syntheticHistory(); input.candles.at(-1).complete = false;
    const history = parseHistory(input);
    expect(chartAt(history, '1d', history.captured_at + 100 * DAY).candles).toHaveLength(209);
    expect(chartAt(history).candles).toHaveLength(29);
  });

  it('clips replay to completed candles and excludes a partial terminal week', () => {
    const history = parseHistory(syntheticHistory());
    const cutoff = history.candles[17].end;
    expect(chartAt(history, '1d', cutoff).candles).toHaveLength(18);
    expect(chartAt(history, '1w', cutoff).candles).toHaveLength(2);
  });

  it('reports pivots only after their required right-side bars close', () => {
    const history = parseHistory(syntheticHistory());
    const chart = chartAt(history);
    const all = confirmedPivots(chart.candles).pivots;
    expect(all.length).toBeGreaterThan(3);
    const first = all[0];
    expect(first.confirmed_at).toBe(first.time + 3 * WEEK);
    expect(confirmedPivots(chartAt(history, '1w', first.confirmed_at - 1).candles).pivots.some((p) => p.id === first.id)).toBe(false);
    expect(confirmedPivots(chartAt(history, '1w', first.confirmed_at).candles).pivots.some((p) => p.id === first.id)).toBe(true);
  });

  it('cannot change an as-of analysis when only future prices are poisoned', () => {
    const input = syntheticHistory();
    const cutoff = input.candles[125].end;
    const expected = confirmedPivots(chartAt(parseHistory(input), '1w', cutoff).candles);
    input.candles.filter((row) => row.end > cutoff).forEach((row) => {
      row.open *= 100; row.high *= 100; row.low *= 100; row.close *= 100;
    });
    expect(confirmedPivots(chartAt(parseHistory(input), '1w', cutoff).candles)).toEqual(expected);
  });

  it('does not confirm swings across a missing calendar interval', () => {
    const bars = chartAt(parseHistory(syntheticHistory())).candles;
    const pivot = confirmedPivots(bars).pivots[0];
    const missing = bars.filter((row) => row.time !== pivot.time + WEEK);
    expect(confirmedPivots(missing).pivots.some((p) => p.id === pivot.id)).toBe(false);
  });

  it('withholds bars that qualify as both a high and low', () => {
    const bars = [
      { time: 0, end: DAY, high: 10, low: 5 },
      { time: DAY, end: 2 * DAY, high: 20, low: 1 },
      { time: 2 * DAY, end: 3 * DAY, high: 12, low: 6 },
    ];
    expect(confirmedPivots(bars, { left: 1, right: 1, interval: DAY })).toEqual({ pivots: [], ambiguous: 1 });
  });
});

describe('conditional Fibonacci geometry', () => {
  const anchors = [
    { id: 'a', type: 'low', time: 0, price: 10, confirmed_at: 2 * DAY },
    { id: 'b', type: 'high', time: 5 * DAY, price: 20, confirmed_at: 7 * DAY },
    { id: 'c', type: 'low', time: 10 * DAY, price: 15, confirmed_at: 12 * DAY },
  ];

  it('calculates retracements from B and extensions from C without a target date', () => {
    const result = fibScenario(anchors);
    expect(result).toMatchObject({ direction: 'up', retracement: 0.5, invalidation: 10, available_at: 12 * DAY, status: 'conditional' });
    expect(result.targets[0].price).toBe(25);
    expect(result.targets[2].price).toBeCloseTo(31.18);
    expect(result.pullback_zone[0]).toBeCloseTo(13.82);
    expect(result).not.toHaveProperty('target_time');
  });

  it('handles a downward leg symmetrically', () => {
    const flipped = anchors.map((anchor) => ({ ...anchor, type: anchor.type === 'low' ? 'high' : 'low', price: 30 - anchor.price }));
    const result = fibScenario(flipped);
    expect(result.direction).toBe('down');
    expect(result.targets[0].price).toBe(5);
    expect(result.targets.every((target) => target.price > 0)).toBe(true);
  });

  it('rejects out-of-order and invalidated retracement structures', () => {
    expect(fibScenario([anchors[1], anchors[0], anchors[2]]).error).toBeTruthy();
    expect(fibScenario([anchors[0], anchors[1], { ...anchors[2], price: 9 }]).error).toBeTruthy();
  });

  it('does not retroactively grade touches that preceded anchor confirmation', () => {
    expect(fibScenario(anchors, [{ time: 11 * DAY, high: 40, low: 1 }]).status).toBe('conditional');
    expect(fibScenario(anchors, [{ time: 12 * DAY, high: 40, low: 1 }]).status).toBe('both_touched_order_unknown');
  });

  it('uses the latest alternating swings rather than searching for attractive geometry', () => {
    const pivots = [...anchors, { id: 'd', type: 'high', time: 20 * DAY, price: 30, confirmed_at: 22 * DAY }];
    const selected = defaultAnchors(pivots);
    expect(selected).toEqual(['b', 'c', 'd']);
    expect(fibScenario(selected.map((id) => pivots.find((p) => p.id === id))).error).toBeTruthy();
  });

  it('preserves quote units and small-coin precision', () => {
    expect(priceText(0.00001234)).toBe('$0.00001234');
    expect(priceText(12, 'USDT')).toBe('12 USDT');
    expect(priceText(null)).toBe('Unavailable');
  });
});
