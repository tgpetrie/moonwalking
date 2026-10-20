// Public, unsigned Coinbase Exchange GETs only. No account APIs or data stores.
// Docs: https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-candles
import { DAY, HISTORY_SCHEMA, parseHistory } from './macroChart.js';
import { CANDLE_SETTLEMENT_SECONDS, HISTORY_RECHECK_MS, requireCurrentHistory } from './chartFreshness.js';

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
          response = await fetcher(`${BASE}${path}`, { method: 'GET', cache: 'no-store', credentials: 'omit', signal: controller.signal });
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
  async function products(signal, force = false) {
    if (catalog && !force) return catalog;
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
    async history(productId, { signal, onProgress = () => {}, force = false, includeLatestTrade = false } = {}) {
      const rows = await products(signal, force);
      const product = rows.find((p) => p.id === productId);
      if (!product) throw new Error('Select a coin from the search results.');
      const end = Math.floor((now() / 1000 - CANDLE_SETTLEMENT_SECONDS) / DAY) * DAY;
      const key = `${productId}:${end}`;
      const exact = cache.get(key);
      if (!force && !includeLatestTrade && exact && now() - Date.parse(exact.source.fetched_at) < HISTORY_RECHECK_MS) {
        check(signal); return requireCurrentHistory(exact, now());
      }
      const previous = [...cache.values()].filter((p) => p.instrument.product_id === productId && p.captured_at <= end).at(-1);
      const firstRequest = previous ? Math.max(START, previous.candles.at(-1).time - 6 * DAY) : START;
      const total = Math.ceil((end - firstRequest) / (299 * DAY));
      if (total < 1 || total > 40) throw new Error('The requested history range is unsupported.');
      const candles = new Map();
      for (const p of previous?.candles ?? []) {
        if (p.time < firstRequest) candles.set(p.time, [p.time, p.low, p.high, p.open, p.close, p.volume]);
      }
      let completed = 0;
      for (let start = firstRequest; start < end; start += 299 * DAY) {
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
      const result = requireCurrentHistory(parseHistory({ schema_version: HISTORY_SCHEMA,
        instrument: { product_id: product.id, symbol: product.symbol, venue: 'Coinbase Exchange', quote_currency: 'USD' },
        interval_seconds: DAY, captured_at: end,
        candles: [...candles.values()].map(([start, low, high, open, close, volume]) =>
          ({ start, end: start + DAY, low, high, open, close, volume, complete: true })),
        source: { contract: 'coinbase-public-browser/v1', fetched_at: new Date(now()).toISOString(),
          requested_start: new Date(firstRequest * 1000).toISOString(), requested_end_exclusive: new Date(end * 1000).toISOString(),
          reused_earlier_history: Boolean(previous),
          stitched: false, scope: 'Available Coinbase USD history only; not all-time or verified token-migration coverage.' } }), now());
      // A quote is separate context; it never replaces a completed-candle close.
      if (includeLatestTrade) {
        try {
          const quote = await get(`/products/${encodeURIComponent(productId)}/ticker`, signal);
          const price = Number(quote.price);
          const tradeTime = typeof quote.time === 'string' ? Date.parse(quote.time) : NaN;
          if (!['number', 'string'].includes(typeof quote.price) || !Number.isFinite(price) || price <= 0
            || !Number.isFinite(tradeTime) || tradeTime > now() + 60000) throw new Error('Coinbase returned an invalid latest trade.');
          result.source.latest_trade = { price, trade_at: quote.time, checked_at: new Date(now()).toISOString(),
            source_url: `${BASE}/products/${encodeURIComponent(productId)}/ticker` };
        } catch (error) {
          check(signal);
          result.source.latest_trade = null;
          result.source.latest_trade_error = error.message;
        }
      }
      requireCurrentHistory(result, now());
      cache.set(key, result);
      if (cache.size > 3) cache.delete(cache.keys().next().value);
      onProgress({ completed: total, total, candles: candles.size });
      return result;
    },
  };
}

export const publicHistoryClient = createPublicHistoryClient();
