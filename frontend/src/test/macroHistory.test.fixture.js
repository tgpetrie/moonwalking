// Synthetic values for tests only. This fixture is never loaded by the product.
import { DAY, HISTORY_SCHEMA } from '../utils/macroChart.js';

export function syntheticHistory() {
  const start = Date.UTC(2024, 0, 1) / 1000; // Monday
  const weeks = [12, 11, 10, 9, 10, 11, 12, 14, 17, 20, 19, 18, 17, 16, 15, 16, 17, 18, 20, 22, 24, 23, 22, 21, 20, 19, 20, 21, 22, 23];
  const candles = weeks.flatMap((value, week) => Array.from({ length: 7 }, (_, day) => {
    const time = start + (week * 7 + day) * DAY;
    const close = value + day * 0.01;
    return { start: time, end: time + DAY, open: close - 0.1, high: close + 0.4, low: close - 0.4, close, volume: 100 + day, complete: true };
  }));
  return {
    schema_version: HISTORY_SCHEMA,
    instrument: { product_id: 'TEST-USD', symbol: 'TEST', venue: 'Synthetic test fixture', quote_currency: 'USD' },
    interval_seconds: DAY, captured_at: candles.at(-1).end, candles,
  };
}

export function syntheticMarketHistory() {
  const input = syntheticHistory();
  return {
    contract: 'moonwalking.market-history/v1', series_id: 'test-venue:TEST-USD:1d',
    as_of: new Date(input.captured_at * 1000).toISOString().replace('.000Z', 'Z'),
    asset: { symbol: 'TEST' },
    market: { venue: 'Synthetic test fixture', product_id: 'TEST-USD', base_currency: 'TEST', quote_currency: 'USD', price_unit: 'USD', volume_unit: 'TEST' },
    interval: { granularity: '1d', seconds: DAY, bucket_timestamp: 'open' },
    provenance: { stitched: false, source: 'synthetic-tests-only' }, coverage: {},
    candles: input.candles.map((row) => ({ t: new Date(row.start * 1000).toISOString().replace('.000Z', 'Z'), o: row.open, h: row.high, l: row.low, c: row.close, v: row.volume, complete: row.complete, flags: [] })),
  };
}
