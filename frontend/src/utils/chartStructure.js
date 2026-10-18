// Geometry foundations only. These functions do not classify Elliott waves,
// discover a profitable channel, or infer probabilities from a fitted line.
import { WEEK, confirmedPivots } from './macroChart.js';

const positive = (n) => typeof n === 'number' && Number.isFinite(n) && n > 0;
const timestamp = (n) => Number.isSafeInteger(n) && n >= 0;

export function structurePivots(candles, { mode = 'wick', left = 2, right = 2, interval = WEEK } = {}) {
  if (!['wick', 'body'].includes(mode)) throw new Error('Choose wick or body anchors.');
  const input = mode === 'wick' ? candles : candles.map((c) => ({
    ...c, high: Math.max(c.open, c.close), low: Math.min(c.open, c.close),
    // A body is a bucket-level reference, not the wick's constituent day.
    high_time: c.time, low_time: c.time,
  }));
  const detected = confirmedPivots(input, { left, right, interval });
  const originals = new Map(candles.map((c) => [c.time, c]));
  return { ...detected, mode, pivots: detected.pivots.map((p) => {
    const c = originals.get(p.time);
    return { ...p, price_basis: mode, wick_price: c[p.type],
      body_price: p.type === 'high' ? Math.max(c.open, c.close) : Math.min(c.open, c.close) };
  }) };
}

export function trendlineAt(anchors, time, { asOf, scale = 'log' } = {}) {
  if (!Array.isArray(anchors) || anchors.length !== 2 || !timestamp(time) || !timestamp(asOf)
    || !['log', 'linear'].includes(scale)) throw new Error('Provide two anchors, an evaluation time and an explicit as-of cutoff.');
  const [a, b] = anchors;
  if (!anchors.every((p) => p && timestamp(p.time) && positive(p.price)
      && timestamp(p.confirmed_at) && p.confirmed_at >= p.time)
    || b.time <= a.time) throw new Error('Anchors require positive prices and increasing timestamps.');
  const availableAt = Math.max(a.confirmed_at, b.confirmed_at);
  if (availableAt > asOf) throw new Error('Both anchors must be confirmed by the as-of cutoff.');
  const fraction = (time - a.time) / (b.time - a.time);
  const price = scale === 'log'
    ? Math.exp(Math.log(a.price) + fraction * (Math.log(b.price) - Math.log(a.price)))
    : a.price + fraction * (b.price - a.price);
  if (!positive(price)) throw new Error('This extrapolation has no finite positive price.');
  return { price, time, scale, as_of: asOf, available_at: availableAt,
    extrapolated: fraction < 0 || fraction > 1,
    interpretation: time >= asOf ? 'hypothetical_projection' : 'fitted_historical_reference' };
}

export function trendlineSensitivity(anchors, time, options) {
  if (!Array.isArray(anchors) || anchors.length !== 2
    || !anchors.every((p) => positive(p?.wick_price) && positive(p?.body_price))) {
    throw new Error('Both anchors need explicit wick and body prices.');
  }
  const variants = ['wick', 'body'].flatMap((first) => ['wick', 'body'].map((second) => {
    const modes = [first, second];
    const selected = anchors.map((p, i) => ({ ...p, price: p[`${modes[i]}_price`] }));
    return { conventions: modes, ...trendlineAt(selected, time, options) };
  }));
  const lower = Math.min(...variants.map((v) => v.price));
  const upper = Math.max(...variants.map((v) => v.price));
  return { lower, upper, spread_percent_of_lower: (upper / lower - 1) * 100, variants,
    interpretation: 'Anchor-convention sensitivity; not a statistical confidence interval.' };
}
