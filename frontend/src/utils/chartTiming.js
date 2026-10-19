import { DAY } from './macroChart.js';

const positive = (n) => Number.isFinite(n) && n > 0;
const timestamp = (n) => Number.isSafeInteger(n) && n >= 0;

export function historicalLegs(anchors, asOf) {
  if (!timestamp(asOf)) return [];
  const eligible = anchors.filter((p) => timestamp(p.time) && timestamp(p.confirmed_at)
    && p.confirmed_at >= p.time && p.confirmed_at <= asOf && positive(p.price));
  return eligible.slice(1).flatMap((to, i) => {
    const from = eligible[i];
    const start = from.extreme_time ?? from.time;
    const end = to.extreme_time ?? to.time;
    if (!timestamp(start) || !timestamp(end) || end <= start) return [];
    return [{ label: `${from.label}–${to.label}`, start, end, from: from.price, to: to.price,
      days: (end - start) / DAY, change_percent: (to.price / from.price - 1) * 100,
      available_at: Math.max(from.confirmed_at, to.confirmed_at), focus_start: start, focus_end: end }];
  });
}

// A touch means candle-range overlap, not continuous intraday residence or a fill.
export function levelEpisodes(candles, pivot, { asOf, widthPercent = 1 } = {}) {
  if (!timestamp(asOf) || !positive(pivot?.price) || !timestamp(pivot.time) || !timestamp(pivot.confirmed_at)
    || pivot.confirmed_at < pivot.time
    || pivot.confirmed_at > asOf || !positive(widthPercent) || widthPercent > 10) {
    return { error: 'A confirmed level, replay cutoff and inspection width are required.', episodes: [] };
  }
  const lower = pivot.price * (1 - widthPercent / 100);
  const upper = pivot.price * (1 + widthPercent / 100);
  const rows = candles.filter((c) => c.end <= asOf).sort((a, b) => a.time - b.time);
  if (rows.some((c, i) => !timestamp(c.time) || c.time % DAY || c.end !== c.time + DAY
    || !positive(c.low) || !positive(c.high) || !positive(c.close) || c.low > c.close || c.high < c.close
    || (i > 0 && rows[i - 1].time === c.time))) {
    return { error: 'Daily reaction history is invalid.', episodes: [] };
  }
  const side = (c) => !c ? 'unknown' : c.high < lower ? 'below' : c.low > upper ? 'above' : 'inside';
  const groups = [];
  for (let i = 0; i < rows.length; i += 1) {
    const c = rows[i];
    if (c.time < pivot.confirmed_at || c.low > upper || c.high < lower) continue;
    const last = groups.at(-1);
    if (last && last.last_index === i - 1 && rows[last.last_index].end === c.time) last.last_index = i;
    else groups.push({ first_index: i, last_index: i });
  }
  const episodes = groups.map(({ first_index: first, last_index: last }) => {
    const initial = rows[first]; const final = rows[last];
    const prior = rows[first - 1]?.end === initial.time ? rows[first - 1] : null;
    const after = rows[last + 1];
    const exit = after?.time === final.end ? side(after) : after ? 'gap' : 'pending';
    const following = rows.slice(last + 1, last + 8);
    const hasGap = following.some((c, i) => c.time !== final.end + i * DAY);
    const status = hasGap ? 'gap' : following.length === 7 ? 'complete' : 'pending';
    return { start: initial.time, end: final.end, last_touch: final.time,
      touch_days: last - first + 1, approach: side(prior), exit,
      exit_time: ['above', 'below'].includes(exit) ? after.time : null,
      next_day_close: after?.time === final.end ? after.close : null,
      followup_at: final.end + 7 * DAY, followup_status: status,
      return_7d_percent: status === 'complete' ? (following[6].close / final.close - 1) * 100 : null,
      focus_start: initial.time, focus_end: status === 'complete' ? following[6].time : final.time };
  });
  const expectedDays = Math.floor((asOf - pivot.confirmed_at) / DAY);
  const observedDays = rows.filter((c) => c.time >= pivot.confirmed_at).length;
  return { lower, upper, width_percent: widthPercent, available_at: pivot.confirmed_at,
    missing_days: Math.max(0, expectedDays - observedDays), episodes };
}
