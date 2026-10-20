import { DAY, WEEK, confirmedPivots } from './macroChart.js';

// Descriptive observations, not a forecast. Lookback spans are display choices,
// not optimized thresholds. Never fall back to distant macro ratios.
export function nextRunMap(candles, { asOf, confirmation = 2, lookbackDays = 365, interval = DAY } = {}) {
  if (![DAY, WEEK].includes(interval)) throw new Error('Use daily or complete weekly candles.');
  const completed = candles.filter((c) => c.end <= asOf && c.complete !== false);
  const close = completed.at(-1);
  if (!close) return { reference: null, above: [], below: [], at: [], ambiguous: 0 };
  const start = Math.max(completed[0].time, close.end - lookbackDays * DAY);
  const detected = confirmedPivots(completed, { left: confirmation, right: confirmation, interval });
  const eligible = detected.pivots.filter((p) => p.time >= start && p.confirmed_at <= close.end);
  const unique = (list) => [...new Map([...list].sort((a, b) => a.confirmed_at - b.confirmed_at)
    .map((p) => [p.price, p])).values()];
  const decorate = (rows, prefix) => rows.slice(0, 3).map((p, i) => ({ ...p,
    label: `${prefix}${i + 1}`, display_label: `Prior ${p.type} ${i + 1}`,
    distance_percent: (p.price / close.close - 1) * 100 }));
  const highs = unique(eligible.filter((p) => p.type === 'high')).sort((a, b) => a.price - b.price);
  const lows = unique(eligible.filter((p) => p.type === 'low')).sort((a, b) => b.price - a.price);
  return { reference: close, start, end: close.end, lookback_days: lookbackDays,
    confirmation, interval_seconds: interval, ambiguous: detected.ambiguous,
    above: decorate(highs.filter((p) => p.price > close.close), 'H'),
    below: decorate(lows.filter((p) => p.price < close.close), 'L'),
    outside_range: { above: highs.filter((p) => p.price > close.high).slice(0, 3),
      below: lows.filter((p) => p.price < close.low).slice(0, 3) },
    at: unique(eligible.filter((p) => p.price === close.close)),
  };
}
