import { DAY, confirmedPivots } from './macroChart.js';

// A descriptive watchlist, not a forecast. One year is a visible scope choice,
// not an optimized trading threshold. Never fall back to distant macro ratios.
export function nextRunMap(candles, { asOf, confirmation = 2, lookbackDays = 365 } = {}) {
  const completed = candles.filter((c) => c.end <= asOf);
  const close = completed.at(-1);
  if (!close) return { reference: null, above: [], below: [], at: [], ambiguous: 0 };
  const start = Math.max(completed[0].time, close.end - lookbackDays * DAY);
  const detected = confirmedPivots(completed, { left: confirmation, right: confirmation, interval: DAY });
  const eligible = detected.pivots.filter((p) => p.time >= start && p.confirmed_at <= close.end);
  const unique = (list) => [...new Map([...list].sort((a, b) => a.confirmed_at - b.confirmed_at)
    .map((p) => [p.price, p])).values()];
  const decorate = (rows, prefix) => rows.slice(0, 3).map((p, i) => ({ ...p,
    label: `${prefix}${i + 1}`, distance_percent: (p.price / close.close - 1) * 100 }));
  return { reference: close, start, end: close.end, lookback_days: lookbackDays,
    confirmation, ambiguous: detected.ambiguous,
    above: decorate(unique(eligible.filter((p) => p.type === 'high' && p.price > close.close))
      .sort((a, b) => a.price - b.price), 'R'),
    below: decorate(unique(eligible.filter((p) => p.type === 'low' && p.price < close.close))
      .sort((a, b) => b.price - a.price), 'S'),
    at: unique(eligible.filter((p) => p.price === close.close)),
  };
}
