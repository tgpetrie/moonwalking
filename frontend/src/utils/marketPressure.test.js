import { describe, expect, it } from 'vitest';
import { getMarketPressure } from './marketPressure';

describe('getMarketPressure availability', () => {
  it('keeps an absent payload unavailable without a synthetic Neutral 50/100', () => {
    expect(getMarketPressure(null)).toMatchObject({
      available: false,
      breadth_available: false,
      index: null,
      label: null,
      score01: null,
      heat: null,
      breadth_up: null,
      components: { breadth: null },
    });
  });

  it('recognizes the zero-symbol warming fallback as unavailable', () => {
    const pressure = getMarketPressure({
      market_pressure: {
        index: 50,
        label: 'Neutral',
        score01: 0.5,
        breadth_up: 0,
        components: { breadth: 0 },
        symbol_count: 0,
      },
    });

    expect(pressure.available).toBe(false);
    expect(pressure.index).toBeNull();
    expect(pressure.label).toBeNull();
    expect(pressure.breadth_up).toBeNull();
    expect(pressure.components.breadth).toBeNull();
  });

  it('does not coerce explicit null breadth to zero', () => {
    const pressure = getMarketPressure({
      market_pressure: {
        index: 61,
        breadth_up: null,
        components: { breadth: null },
        symbol_count: 12,
      },
    });

    expect(pressure.available).toBe(true);
    expect(pressure.breadth_available).toBe(false);
    expect(pressure.breadth_up).toBeNull();
    expect(pressure.components.breadth).toBeNull();
  });

  it('preserves measured zero breadth when markets were actually observed', () => {
    const pressure = getMarketPressure({
      market_pressure: {
        index: 25,
        label: 'Cautious',
        score01: 0.25,
        breadth_up: 0,
        breadth_down: 1,
        components: { breadth: 0 },
        symbol_count: 12,
      },
    });

    expect(pressure).toMatchObject({
      available: true,
      breadth_available: true,
      index: 25,
      label: 'Cautious',
      breadth_up: 0,
      breadth_down: 1,
      components: { breadth: 0 },
    });
  });

  it('preserves present supportive breadth and canonical pressure values', () => {
    const pressure = getMarketPressure({
      market_pressure: {
        index: 72,
        label: 'Risk-On',
        score01: 0.72,
        breadth_up: 0.64,
        breadth_down: 0.28,
        components: { breadth: 0.64, persistence: 0.4 },
        symbol_count: 50,
        ts: 1_700_100_000,
      },
    });

    expect(pressure).toMatchObject({
      available: true,
      breadth_available: true,
      index: 72,
      label: 'Risk-On',
      score01: 0.72,
      heat: 72,
      breadth_up: 0.64,
      breadth_down: 0.28,
      components: { breadth: 0.64, persistence: 0.4 },
      symbol_count: 50,
      ts: 1_700_100_000,
    });
  });
});
