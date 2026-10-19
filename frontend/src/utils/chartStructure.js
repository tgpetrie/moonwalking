// Geometry foundations only. These functions do not classify Elliott waves,
// discover a profitable channel, or infer probabilities from a fitted line.
import { WEEK, confirmedPivots } from './macroChart.js';

const positive = (n) => typeof n === 'number' && Number.isFinite(n) && n > 0;
const timestamp = (n) => Number.isSafeInteger(n) && n >= 0;

export const MACRO_RATIOS = [0, 0.236, 0.309, 0.382, 0.5, 0.618, 0.702, 0.786, 1, 1.618, 2.618, 3.618, 4.236];

export function defaultMacroAnchors(pivots) {
  const ordered = [...pivots].sort((a, b) => a.time - b.time);
  const high = ordered.filter((p) => p.type === 'high').reduce((best, p) => !best || p.price > best.price ? p : best, null);
  if (!high) return ['', ''];
  const low = ordered.filter((p) => p.type === 'low' && p.time > high.time)
    .reduce((best, p) => !best || p.price < best.price ? p : best, null);
  return [high.id, low?.id || ''];
}

export function macroRange(high, low, { asOf } = {}) {
  if (!high || !low) return { error: 'Select a confirmed high and a later confirmed low.' };
  if (high.type !== 'high' || low.type !== 'low' || !timestamp(high.time) || !timestamp(low.time)
    || low.time <= high.time || !positive(high.price) || !positive(low.price) || low.price >= high.price) {
    return { error: 'The macro range needs a high followed by a lower low.' };
  }
  if (!timestamp(asOf) || ![high, low].every((p) => timestamp(p.confirmed_at)
    && p.confirmed_at >= p.time && p.confirmed_at <= asOf)) {
    return { error: 'Both macro anchors must be confirmed by the replay cutoff.' };
  }
  const span = high.price - low.price;
  const levels = MACRO_RATIOS.map((ratio) => ({ ratio, price: low.price + ratio * span }));
  if (levels.some((p) => !positive(p.price))) return { error: 'The selected macro range exceeds numeric limits.' };
  return { anchors: [high, low], levels, available_at: Math.max(high.confirmed_at, low.confirmed_at),
    recovery_band: [low.price + 0.5 * span, low.price + 0.786 * span],
    interpretation: 'Conditional recovery reference; no forecast date or measured probability.' };
}

// A–D are descriptive anchor names, not an Elliott-wave classification.
export function historicalMacro(pivots, range, { asOf } = {}) {
  const checked = macroRange(range?.anchors?.[0], range?.anchors?.[1], { asOf });
  if (checked.error) return { error: checked.error, anchors: [] };
  const [c, d] = checked.anchors;
  const eligible = pivots.filter((p) => timestamp(p.time) && positive(p.price)
    && timestamp(p.confirmed_at) && p.confirmed_at >= p.time && p.confirmed_at <= asOf)
    .sort((a, b) => a.time - b.time);
  const b = eligible.filter((p) => p.type === 'low' && p.time < c.time)
    .reduce((best, p) => !best || p.price < best.price ? p : best, null);
  const a = b && eligible.filter((p) => p.type === 'high' && p.time < b.time)
    .reduce((best, p) => !best || p.price > best.price ? p : best, null);
  const anchors = [a, b, c, d].flatMap((p, i) => p ? [{ ...p, label: 'ABCD'[i] }] : []);
  return { anchors, complete: !!a && !!b,
    available_at: Math.max(...anchors.map((p) => p.confirmed_at)),
    interpretation: 'Historical anchor sequence; not a validated wave count.' };
}

export function recentSwingSequence(pivots, { asOf } = {}) {
  const alternating = [];
  for (const p of [...pivots].filter((p) => timestamp(asOf) && timestamp(p.confirmed_at)
    && p.confirmed_at <= asOf).sort((a, b) => a.time - b.time)) {
    const last = alternating.at(-1);
    if (last?.type === p.type) {
      if (p.type === 'high' ? p.price > last.price : p.price < last.price) alternating[alternating.length - 1] = p;
    } else alternating.push(p);
  }
  return alternating.slice(-4).map((p, i) => ({ ...p, label: 'abcd'[i] }));
}

export function highComparison(range, referencePrice, lastClose, observedHigh = range?.anchors?.[0]?.price) {
  if (range?.error || !positive(range?.anchors?.[0]?.price) || !positive(referencePrice) || !positive(lastClose)) return null;
  if (!positive(observedHigh)) return null;
  const previousHigh = observedHigh;
  return { previous_high: previousHigh, reference: referencePrice,
    relation: referencePrice > previousHigh ? 'above' : referencePrice < previousHigh ? 'below' : 'at',
    percent_from_high: (referencePrice / previousHigh - 1) * 100,
    already_above: lastClose > previousHigh,
    explanation: 'A recovery below the old high and an extension above it are different scenarios. Neither is assigned a likelihood by this geometry.' };
}

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
