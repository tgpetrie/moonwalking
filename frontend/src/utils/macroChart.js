// Chart-history v1: deterministic, local-only calculations. No inferred prices.
export const DAY = 86400;
export const WEEK = 7 * DAY;
export const HISTORY_SCHEMA = 'bhabit.chart-history.v1';
export const MARKET_HISTORY_CONTRACT = 'moonwalking.market-history/v1';
export const RETRACEMENTS = [0.236, 0.309, 0.382, 0.5, 0.618, 0.702, 0.786];
export const EXTENSIONS = [1, 1.272, 1.618];

const finite = (value) => typeof value === 'number' && Number.isFinite(value);
const integer = (value) => Number.isSafeInteger(value) && value >= 0;

// Display transform only: switching scale never changes Fibonacci prices.
export function priceScale(prices, mode = 'log') {
  if (!['linear', 'log'].includes(mode) || !prices.length || prices.some((p) => !finite(p) || p <= 0)) {
    throw new Error('Price scales require a supported mode and positive finite prices.');
  }
  const transform = mode === 'log' ? Math.log : (p) => p;
  const inverse = mode === 'log' ? Math.exp : (p) => p;
  const floor = Math.min(...prices.map(transform));
  const ceiling = Math.max(...prices.map(transform));
  const span = ceiling - floor || Math.max(Math.abs(ceiling) * 0.1, 0.1);
  const min = mode === 'linear' ? Math.max(0, floor - span * 0.08) : floor - span * 0.08;
  const max = ceiling + span * 0.1;
  return {
    position: (price) => (transform(price) - min) / (max - min),
    ticks: Array.from({ length: 6 }, (_, i) => inverse(min + (max - min) * i / 5)),
  };
}

function isoSeconds(value) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/.test(value)) {
    throw new Error('Market-history timestamps must be UTC ISO dates with whole seconds.');
  }
  const time = Date.parse(value) / 1000;
  if (!integer(time) || new Date(time * 1000).toISOString().replace('.000Z', 'Z') !== value) {
    throw new Error('Market history contains an invalid date.');
  }
  return time;
}

function adaptMarketHistory(input) {
  if (input.interval?.granularity !== '1d' || input.interval?.seconds !== DAY
    || input.interval?.bucket_timestamp !== 'open') {
    throw new Error('Load the native daily series. Weekly candles are derived from its complete days.');
  }
  if (input.provenance?.stitched !== false || input.market?.price_unit !== input.market?.quote_currency
    || input.market?.volume_unit !== input.market?.base_currency) {
    throw new Error('History must identify an unstitched series with explicit price and volume units.');
  }
  if (!Array.isArray(input.candles)) throw new Error('Market history must contain a candle array.');
  return {
    schema_version: HISTORY_SCHEMA,
    instrument: {
      product_id: input.market?.product_id, symbol: input.asset?.symbol,
      venue: input.market?.venue, quote_currency: input.market?.quote_currency,
    },
    interval_seconds: DAY, captured_at: isoSeconds(input.as_of),
    candles: input.candles.map((row) => {
      const start = isoSeconds(row.t);
      return { start, end: start + DAY, open: row.o, high: row.h, low: row.l, close: row.c, volume: row.v, complete: row.complete };
    }),
    source: { contract: input.contract, series_id: input.series_id, provenance: input.provenance, coverage: input.coverage },
  };
}

export function parseHistory(input) {
  if (input?.contract === MARKET_HISTORY_CONTRACT) input = adaptMarketHistory(input);
  if (!input || input.schema_version !== HISTORY_SCHEMA) {
    throw new Error('This file does not use the supported chart-history format.');
  }
  const instrument = input.instrument;
  if (!instrument || !['product_id', 'symbol', 'venue', 'quote_currency'].every(
    (field) => typeof instrument[field] === 'string' && instrument[field].trim(),
  ) || !/^[A-Z0-9]{1,20}$/.test(instrument.symbol)
    || !/^[A-Z0-9]{2,12}$/.test(instrument.quote_currency)) {
    throw new Error('History must identify its symbol, instrument, venue and quote currency.');
  }
  if (input.interval_seconds !== DAY || !integer(input.captured_at)) {
    throw new Error('Provide UTC daily candles and a captured_at timestamp in Unix seconds.');
  }
  if (!Array.isArray(input.candles) || !input.candles.length || input.candles.length > 50000) {
    throw new Error('Provide between 1 and 50,000 daily candles.');
  }
  const seen = new Set();
  const candles = input.candles.map((row, index) => {
    const validTimes = integer(row?.start) && row.start % DAY === 0
      && integer(row.end) && row.end - row.start === DAY && row.start <= input.captured_at;
    const validPrices = ['open', 'high', 'low', 'close'].every(
      (field) => finite(row?.[field]) && row[field] > 0,
    ) && row.low <= Math.min(row.open, row.close)
      && row.high >= Math.max(row.open, row.close) && row.low <= row.high;
    if (!validTimes || !validPrices || !finite(row?.volume) || row.volume < 0
      || typeof row.complete !== 'boolean' || (row.complete && row.end > input.captured_at)) {
      throw new Error(`Candle ${index + 1} has invalid prices, timestamps or completeness.`);
    }
    if (seen.has(row.start)) throw new Error('History contains duplicate candle timestamps.');
    seen.add(row.start);
    return {
      time: row.start, end: row.end, open: row.open, high: row.high,
      low: row.low, close: row.close, volume: row.volume, complete: row.complete,
      high_time: row.start, low_time: row.start,
    };
  }).sort((a, b) => a.time - b.time);
  return {
    schema_version: HISTORY_SCHEMA,
    instrument: Object.fromEntries(['product_id', 'symbol', 'venue', 'quote_currency'].map(
      (field) => [field, instrument[field].trim()],
    )),
    captured_at: input.captured_at,
    source: input.source || null,
    candles,
  };
}

export function mondayStart(time) {
  // 1970-01-01 was Thursday; Unix week zero starts on Monday 1969-12-29.
  return Math.floor((time + 3 * DAY) / WEEK) * WEEK - 3 * DAY;
}

export function aggregateWeeks(daily) {
  const buckets = new Map();
  for (const row of daily) {
    const start = mondayStart(row.time);
    if (!buckets.has(start)) buckets.set(start, []);
    buckets.get(start).push(row);
  }
  return [...buckets.entries()].sort(([a], [b]) => a - b).map(([time, rows]) => {
    const ordered = [...rows].sort((a, b) => a.time - b.time);
    return {
      time, end: time + WEEK, open: ordered[0].open, close: ordered.at(-1).close,
      high: Math.max(...ordered.map((row) => row.high)),
      low: Math.min(...ordered.map((row) => row.low)),
      high_time: ordered.reduce((a, b) => a.high >= b.high ? a : b).time,
      low_time: ordered.reduce((a, b) => a.low <= b.low ? a : b).time,
      volume: ordered.reduce((sum, row) => sum + row.volume, 0),
      complete: ordered.length === 7 && ordered.every(
        (row, index) => row.complete && row.time === time + index * DAY,
      ),
      day_count: ordered.length,
    };
  });
}

export function chartAt(history, timeframe = '1w', asOf = history.captured_at) {
  if (!['1d', '1w'].includes(timeframe) || !integer(asOf)) throw new Error('Invalid chart date or timeframe.');
  const cutoff = Math.min(asOf, history.captured_at);
  const daily = history.candles.filter((row) => row.complete && row.end <= cutoff);
  const weekly = aggregateWeeks(daily);
  const candles = timeframe === '1w' ? weekly.filter((row) => row.complete && row.end <= cutoff) : daily;
  const expected = daily.length ? Math.round((daily.at(-1).time - daily[0].time) / DAY) + 1 : 0;
  return {
    candles, as_of: cutoff, interval_seconds: timeframe === '1w' ? WEEK : DAY,
    missing_days: expected - daily.length,
    excluded_weeks: weekly.filter((row) => !row.complete || row.end > cutoff).length,
    excluded_candles: history.candles.filter((row) => row.time < cutoff && !row.complete).length,
  };
}

export function confirmedPivots(candles, { left = 2, right = 2, interval = WEEK } = {}) {
  if (![left, right].every((n) => Number.isInteger(n) && n >= 1 && n <= 12)) {
    throw new Error('Pivot confirmation requires 1–12 bars on each side.');
  }
  const pivots = [];
  let ambiguous = 0;
  for (let i = left; i + right < candles.length; i += 1) {
    const window = candles.slice(i - left, i + right + 1);
    if (!window.every((row, index) => index === 0 || row.time - window[index - 1].time === interval)) continue;
    const row = candles[i];
    const peers = window.filter((_, index) => index !== left);
    const high = peers.every((peer) => row.high > peer.high);
    const low = peers.every((peer) => row.low < peer.low);
    if (high && low) { ambiguous += 1; continue; }
    if (!high && !low) continue;
    const type = high ? 'high' : 'low';
    pivots.push({
      id: `${type}-${row.time}`, type, time: row.time, price: row[type],
      extreme_time: row[`${type}_time`] ?? row.time,
      confirmed_at: candles[i + right].end,
    });
  }
  return { pivots, ambiguous };
}

export function defaultAnchors(pivots) {
  const alternating = [];
  for (const pivot of pivots) {
    const last = alternating.at(-1);
    if (last?.type === pivot.type) {
      if ((pivot.type === 'high' && pivot.price > last.price)
        || (pivot.type === 'low' && pivot.price < last.price)) alternating[alternating.length - 1] = pivot;
    } else alternating.push(pivot);
  }
  // Choose the most recent structural triple, even when it fails geometry.
  // Do not search back for a more attractive-looking completed trade.
  return alternating.slice(-3).map((pivot) => pivot.id);
}

export function fibScenario(anchors, candles = []) {
  if (anchors.length !== 3 || anchors.some((a) => !a)) return { error: 'Choose three confirmed turning points to map a scenario.' };
  const [a, b, c] = anchors;
  if (!(a.time < b.time && b.time < c.time)) return { error: 'Anchor dates must follow A, then B, then C.' };
  const bullish = a.type === 'low' && b.type === 'high' && c.type === 'low';
  const bearish = a.type === 'high' && b.type === 'low' && c.type === 'high';
  const delta = b.price - a.price;
  const retrace = (b.price - c.price) / delta;
  if ((!bullish && !bearish) || !Number.isFinite(retrace) || retrace <= 0 || retrace >= 1
    || (bullish && delta <= 0) || (bearish && delta >= 0)) {
    return { error: 'These anchors do not describe a rise/pullback or decline/rebound within the original leg.' };
  }
  const availableAt = Math.max(...anchors.map((anchor) => anchor.confirmed_at));
  const levels = RETRACEMENTS.map((ratio) => ({ ratio, price: b.price - ratio * delta }));
  const targets = EXTENSIONS.map((ratio) => ({ ratio, price: c.price + ratio * delta })).filter((level) => level.price > 0);
  if (!targets.length) return { error: 'This extension has no positive price target.' };
  const after = candles.filter((row) => row.time >= availableAt);
  const invalidated = after.some((row) => bullish ? row.low <= a.price : row.high >= a.price);
  const touched = after.some((row) => bullish ? row.high >= targets[0].price : row.low <= targets[0].price);
  return {
    direction: bullish ? 'up' : 'down', available_at: availableAt, anchors,
    retracement: retrace, levels, targets, invalidation: a.price,
    pullback_zone: [b.price - 0.618 * delta, b.price - 0.382 * delta].sort((x, y) => x - y),
    target_zone: [targets[0].price, targets.at(-1).price].sort((x, y) => x - y),
    status: invalidated && touched ? 'both_touched_order_unknown'
      : invalidated ? 'invalidated' : touched ? 'target_touched' : 'conditional',
  };
}

export function priceText(value, currency = 'USD') {
  if (!finite(value)) return 'Unavailable';
  const options = { maximumFractionDigits: value < 0.01 ? 8 : value < 1 ? 5 : 3 };
  if (/^[A-Z]{3}$/.test(currency)) return new Intl.NumberFormat('en-US', {
    ...options, style: 'currency', currency,
  }).format(value);
  return `${new Intl.NumberFormat('en-US', options).format(value)} ${currency}`;
}

export const dateText = (time) => new Date(time * 1000).toISOString().slice(0, 10);
