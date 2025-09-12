// Lightweight API helpers focused on same-origin /api via Vite proxy
const base = '/api';

export async function fetchJson(path, init) {
  const res = await fetch(base + path, { credentials: 'omit', ...init });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`HTTP ${res.status}: ${text || res.statusText}`);
  }
  const ct = res.headers.get('content-type') || '';
  return ct.includes('application/json') ? res.json() : { ok: true, raw: await res.text() };
}

// Watchlist helpers (align with backend contract)
// GET /api/watchlist -> ["BTC","ETH",...]
export async function getWatchlist() {
  const data = await fetchJson('/watchlist');
  if (Array.isArray(data)) return data;
  if (data && Array.isArray(data.watchlist)) return data.watchlist; // tolerate {watchlist:[...]}
  return [];
}

// POST /api/watchlist { symbol, price? }
export async function addToWatchlist(symbol, price) {
  const body = price != null ? { symbol, price } : { symbol };
  return fetchJson('/watchlist', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  });
}

// DELETE /api/watchlist/:symbol
export async function removeFromWatchlist(symbol) {
  const res = await fetchJson(`/watchlist/${encodeURIComponent(symbol)}`, {
    method: 'DELETE',
  });
  // Backend returns { message, watchlist: [...] }
  if (Array.isArray(res)) return res;
  return res && Array.isArray(res.watchlist) ? res.watchlist : [];
}
