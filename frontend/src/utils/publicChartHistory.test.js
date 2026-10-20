import { describe, expect, it, vi } from 'vitest';
import { DAY } from './macroChart.js';
import { createPublicHistoryClient } from './publicChartHistory.js';

// All responses are synthetic. No test makes a network request.
const product = { id: 'TEST-USD', base_currency: 'TEST', quote_currency: 'USD', status: 'online' };
const response = (data, status = 200) => ({ ok: status === 200, status, headers: { get: () => null }, json: async () => data });
const candle = (t) => [t, 1, 3, 2, 2.5, 100];
function fixture(batch, quote) {
  let clock = Date.UTC(2011, 8, 1, 12);
  const calls = [];
  const fetcher = vi.fn(async (url, options) => {
    calls.push({ url, options, time: clock });
    clock += 10;
    if (url.endsWith('/products')) return response([product, { ...product, id: 'WRONG' }]);
    if (url.endsWith('/ticker')) return quote ?? response({ price: '2.6', time: new Date(clock - 120000).toISOString() });
    const start = Date.parse(new URL(url).searchParams.get('start')) / 1000;
    const end = Date.parse(new URL(url).searchParams.get('end')) / 1000;
    return batch ? batch(start, calls.length, end) : response([candle(start), candle(end - DAY)]);
  });
  const client = createPublicHistoryClient({ fetcher, now: () => clock, wait: async (ms) => { clock += ms; } });
  return { client, calls, fetcher, advance: (ms) => { clock += ms; } };
}

describe('public chart history boundary', () => {
  it('discovers only verified USD product identities and caches the catalog', async () => {
    const { client, calls } = fixture();
    expect(await client.search('test')).toMatchObject([{ id: 'TEST-USD', symbol: 'TEST' }]);
    expect(await client.search('other')).toEqual([]);
    expect(await client.search('')).toEqual([]);
    expect(calls).toHaveLength(1);
    expect(calls[0].options).toMatchObject({ method: 'GET', credentials: 'omit' });
  });
  it('backfills explicit bounded windows, spaces requests, excludes open-day extras and never interpolates gaps', async () => {
    const { client, calls } = fixture((start, _, end) => response([candle(start), candle(start), candle(start - DAY), candle(end - DAY), candle(end)]));
    const updates = [];
    const result = await client.history(product.id, { onProgress: (p) => updates.push(p) });
    expect(result.candles).toHaveLength(6);
    expect(result.candles.every((p) => p.end <= result.captured_at && p.complete)).toBe(true);
    expect(result.source.stitched).toBe(false);
    expect(updates.at(-1)).toMatchObject({ completed: 3, total: 3, candles: 6 });
    for (let i = 1; i < calls.length; i += 1) expect(calls[i].time - calls[i - 1].time).toBeGreaterThanOrEqual(1050);
    for (const call of calls.slice(1)) {
      const q = new URL(call.url).searchParams;
      expect((Date.parse(q.get('end')) - Date.parse(q.get('start'))) / 1000).toBeLessThanOrEqual(299 * DAY);
    }
    const length = calls.length;
    expect(await client.history(product.id)).toBe(result);
    expect(calls).toHaveLength(length);
  });
  it('rejects unknown products without inventing a pair or following an arbitrary URL', async () => {
    const { client, calls } = fixture();
    await expect(client.history('https://other.example/secret')).rejects.toThrow(/Select a coin/);
    expect(calls).toHaveLength(1);
  });
  it.each([
    ['malformed', () => response([[0, 1]])],
    ['negative prices', (t) => response([[t, -1, 3, 2, 2, 1]])],
    ['conflicting duplicates', (t) => response([candle(t), [t, 1, 3, 2, 2.6, 100]])],
    ['empty history', () => response([])],
  ])('retains an unavailable result for %s', async (_, batch) => {
    const { client } = fixture(batch);
    await expect(client.history(product.id)).rejects.toThrow();
  });
  it('backs off on a rate response and continues the same bounded window', async () => {
    let attempts = 0;
    const { client, calls } = fixture((start, _, end) => ++attempts === 1 ? response(null, 429) : response([candle(end - DAY)]));
    await client.history(product.id);
    expect(calls[1].url).toBe(calls[2].url);
    expect(calls[2].time - calls[1].time).toBeGreaterThanOrEqual(2000);
  });
  it('stops after bounded provider errors and supports cancellation between pages', async () => {
    const failed = fixture(() => response(null, 503));
    await expect(failed.client.history(product.id)).rejects.toThrow(/503/);
    expect(failed.calls).toHaveLength(4); // catalog plus three attempts
    const { client, calls } = fixture();
    const controller = new AbortController();
    await expect(client.history(product.id, { signal: controller.signal, onProgress: () => controller.abort() })).rejects.toMatchObject({ name: 'AbortError' });
    expect(calls).toHaveLength(1);
  });
  it('does not retry earlier than a long provider pause', async () => {
    const { client, calls } = fixture(() => ({ ...response(null, 429), headers: { get: () => '180' } }));
    await expect(client.history(product.id)).rejects.toThrow(/longer pause/);
    expect(calls).toHaveLength(2);
  });
  it('rechecks a forced run and expired cache using an authoritative overlap rather than the old same-day value', async () => {
    let close = 2.5;
    const { client, calls, advance } = fixture((start, _, end) => response([[start, 1, 3, 2, close, 100], [end - DAY, 1, 3, 2, close, 100]]));
    const first = await client.history(product.id);
    const count = calls.length;
    close = 2.7;
    const refreshed = await client.history(product.id, { force: true });
    expect(refreshed.candles.at(-1).close).toBe(2.7);
    expect(refreshed.source.reused_earlier_history).toBe(true);
    expect(calls.length - count).toBe(2); // catalog and recent tail, not full backfill
    expect(calls.at(-1).options.cache).toBe('no-store');
    expect(first.candles.at(-1).close).toBe(2.5);
    advance(61000);
    const count2 = calls.length;
    expect(await client.history(product.id)).not.toBe(refreshed);
    expect(calls.length - count2).toBe(1);
    advance((86400 + 300) * 1000);
    const nextDay = await client.history(product.id);
    expect(nextDay.captured_at).toBe(first.captured_at + DAY);
    expect(nextDay.candles.at(-1).end).toBe(nextDay.captured_at);
    expect(nextDay.source.reused_earlier_history).toBe(true);
  });
  it('rejects a stale provider tail even with a fresh request cutoff', async () => {
    const { client } = fixture((start) => response([candle(start)]));
    await expect(client.history(product.id)).rejects.toThrow(/expected through.*not published/);
  });
  it('keeps timestamped latest-trade context separate from the completed daily close', async () => {
    const { client } = fixture();
    const result = await client.history(product.id, { includeLatestTrade: true });
    expect(result.source.latest_trade.price).toBe(2.6);
    expect(result.candles.at(-1).close).toBe(2.5);
    expect(Date.parse(result.source.latest_trade.trade_at)).toBeLessThan(Date.parse(result.source.latest_trade.checked_at));
  });
  it('does not fabricate a trade when the ticker is malformed or unavailable', async () => {
    for (const payload of [response({ price: 'bad', time: 'bad' }), response(null, 503)]) {
      const { client } = fixture(undefined, payload);
      const result = await client.history(product.id, { includeLatestTrade: true });
      expect(result.source.latest_trade).toBe(null);
      expect(result.source.latest_trade_error).toBeTruthy();
    }
  });
});
