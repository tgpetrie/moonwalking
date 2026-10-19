// Public, unsigned Coinbase Exchange GETs only. No account APIs or data stores.
// Docs: https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-candles
import { DAY, HISTORY_SCHEMA, parseHistory } from './macroChart.js';

const BASE = 'https://api.exchange.coinbase.com';
const START = Date.UTC(2010, 0, 1) / 1000;
const abortError = () => new DOMException('Cancelled', 'AbortError');
function check(signal) { if (signal?.aborted) throw abortError(); }
function pause(ms, signal) {
  check(signal);
  return new Promise((resolve, reject) => {
    const done = () => { signal?.removeEventListener('abort', abort); resolve(); };
    const timer = setTimeout(done, ms);
    const abort = () => { clearTimeout(timer); signal?.removeEventListener('abort', abort); reject(abortError()); };
    signal?.addEventListener('abort', abort, { once: true });
  });
}

export function createPublicHistoryClient({ fetcher = (...args) => fetch(...args), now = () => Date.now(), wait = pause } = {}) {
  let queue = Promise.resolve();
  let lastFinished = -Infinity;
  let catalog = null;
  const cache = new Map();
  function get(path, signal) {
    const request = queue.catch(() => {}).then(async () => {
      for (let attempt = 0; attempt < 3; attempt += 1) {
        check(signal);
        await wait(Math.max(0, 1050 - (now() - lastFinished)), signal);
        check(signal);
        const controller = new AbortController();
        const cancel = () => controller.abort();
        signal?.addEventListener('abort', cancel, { once: true });
        const timer = setTimeout(cancel, 20000);
        let response;
        try {
          response = await fetcher(`${BASE}${path}`, { method: 'GET', credentials: 'omit', signal: controller.signal });
          if (response.ok) return await response.json();
          if (![429, 503].includes(response.status) || attempt === 2) {
            throw new Error(`Coinbase history is unavailable (HTTP ${response.status}). Try again later.`);
          }
        } catch (error) {
          check(signal);
          if (error.name === 'AbortError') throw new Error('Coinbase took too long to respond. Please try again.');
          throw error;
        } finally {
          lastFinished = now(); clearTimeout(timer); signal?.removeEventListener('abort', cancel);
        }
        const header = response.headers?.get('Retry-After');
        const seconds = header && Number(header);
        const retryMs = header ? (Number.isFinite(seconds) ? seconds * 1000 : Date.parse(header) - now()) : 0;
        if (retryMs > 120000) throw new Error('Coinbase requested a longer pause. Please try again later.');
        await wait(Math.max(2000 * 2 ** attempt, Number.isFinite(retryMs) ? retryMs : 0), signal);
      }
    });
    queue = request.catch(() => {});
    return request;
  }
  async function products(signal) {
    if (catalog) return catalog;
    const rows = await get('/products', signal);
    if (!Array.isArray(rows)) throw new Error('Coinbase returned an invalid coin list.');
    catalog = rows.filter((p) => /^[A-Z0-9]{1,20}$/.test(p.base_currency)
      && p.quote_currency === 'USD' && p.id === `${p.base_currency}-${p.quote_currency}`)
      .map((p) => ({ id: p.id, symbol: p.base_currency, status: p.status, venue: 'Coinbase', quote: 'USD' }));
    return catalog;
  }
  return {
    async search(query, { signal } = {}) {
      const term = query.trim().toUpperCase();
      if (!term) return [];
      const rows = await products(signal);
      check(signal);
      return rows.filter((p) => p.symbol.includes(term)).sort((a, b) =>
        Number(b.symbol === term) - Number(a.symbol === term) || a.symbol.localeCompare(b.symbol)).slice(0, 12);
    },
    async history(productId, { signal, onProgress = () => {} } = {}) {
      const rows = await products(signal);
      const product = rows.find((p) => p.id === productId);
      if (!product) throw new Error('Select a coin from the search results.');
      const end = Math.floor(now() / 1000 / DAY) * DAY;
      const key = `${productId}:${end}`;
      if (cache.has(key)) { check(signal); return cache.get(key); }
      const total = Math.ceil((end - START) / (299 * DAY));
      if (total < 1 || total > 40) throw new Error('The requested history range is unsupported.');
      const candles = new Map();
      let completed = 0;
      for (let start = START; start < end; start += 299 * DAY) {
        check(signal);
        const stop = Math.min(start + 299 * DAY, end);
        onProgress({ completed, total, candles: candles.size });
        const params = new URLSearchParams({ granularity: String(DAY),
          start: new Date(start * 1000).toISOString(), end: new Date(stop * 1000).toISOString() });
        const batch = await get(`/products/${encodeURIComponent(productId)}/candles?${params}`, signal);
        if (!Array.isArray(batch) || batch.length > 300) throw new Error('Coinbase returned an invalid candle batch.');
        for (const row of batch) {
          if (!Array.isArray(row) || row.length !== 6 || row.some((n) => typeof n !== 'number' || !Number.isFinite(n))) {
            throw new Error('Coinbase returned malformed historical prices.');
          }
          const [time, low, high, open, close, volume] = row;
          if (!Number.isSafeInteger(time) || time % DAY || !(0 < low && low <= Math.min(open, close)
            && high >= Math.max(open, close) && volume >= 0)) throw new Error('Coinbase returned invalid daily prices.');
          if (time < start || time >= stop) continue;
          const previous = candles.get(time);
          if (previous && JSON.stringify(previous) !== JSON.stringify(row)) throw new Error('Coinbase returned conflicting candles.');
          candles.set(time, row);
        }
        completed += 1;
      }
      check(signal);
      if (!candles.size) throw new Error(`No daily USD history is available for ${product.symbol} from this source.`);
      const result = parseHistory({ schema_version: HISTORY_SCHEMA,
        instrument: { product_id: product.id, symbol: product.symbol, venue: 'Coinbase Exchange', quote_currency: 'USD' },
        interval_seconds: DAY, captured_at: end,
        candles: [...candles.values()].map(([start, low, high, open, close, volume]) =>
          ({ start, end: start + DAY, low, high, open, close, volume, complete: true })),
        source: { contract: 'coinbase-public-browser/v1', fetched_at: new Date(now()).toISOString(),
          requested_start: new Date(START * 1000).toISOString(), requested_end_exclusive: new Date(end * 1000).toISOString(),
          stitched: false, scope: 'Available Coinbase USD history only; not all-time or verified token-migration coverage.' } });
      cache.set(key, result);
      if (cache.size > 3) cache.delete(cache.keys().next().value);
      onProgress({ completed: total, total, candles: candles.size });
      return result;
    },
  };
}

export const publicHistoryClient = createPublicHistoryClient();
