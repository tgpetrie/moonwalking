import { describe, expect, it, vi } from 'vitest';
import { DAY } from './macroChart.js';
import { createPublicHistoryClient } from './publicChartHistory.js';

// All responses are synthetic. No test makes a network request.
const product = { id: 'TEST-USD', base_currency: 'TEST', quote_currency: 'USD', status: 'online' };
const response = (data, status = 200) => ({ ok: status === 200, status, headers: { get: () => null }, json: async () => data });
const candle = (t) => [t, 1, 3, 2, 2.5, 100];
function fixture(batch) {
  let clock = Date.UTC(2011, 8, 1);
  const calls = [];
  const fetcher = vi.fn(async (url, options) => {
    calls.push({ url, options, time: clock });
    clock += 10;
    if (url.endsWith('/products')) return response([product, { ...product, id: 'WRONG' }]);
    const start = Date.parse(new URL(url).searchParams.get('start')) / 1000;
    return batch ? batch(start, calls.length) : response([candle(start)]);
  });
  const client = createPublicHistoryClient({ fetcher, now: () => clock, wait: async (ms) => { clock += ms; } });
  return { client, calls, fetcher };
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
    const { client, calls } = fixture((start) => response([candle(start), candle(start), candle(start - DAY)]));
    const updates = [];
    const result = await client.history(product.id, { onProgress: (p) => updates.push(p) });
    expect(result.candles).toHaveLength(3);
    expect(result.candles.every((p) => p.end <= result.captured_at && p.complete)).toBe(true);
    expect(result.source.stitched).toBe(false);
    expect(updates.at(-1)).toMatchObject({ completed: 3, total: 3, candles: 3 });
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
    const { client, calls } = fixture((start) => ++attempts === 1 ? response(null, 429) : response([candle(start)]));
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
});
