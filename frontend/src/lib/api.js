// src/lib/api.js
export const API_ORIGIN =
  import.meta.env.VITE_API_ORIGIN ||
  import.meta.env.VITE_API_BASE ||
  'http://127.0.0.1:5002';

async function j(path, init = {}) {
  const url = path.startsWith('http') ? path : `${API_ORIGIN}${path}`;
  const res = await fetch(url, { ...init, headers: { 'accept': 'application/json', ...(init?.headers || {}) } });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export const api = {
  health: () => j('/api/health'),
  metrics: () => j('/api/metrics'),
  topMoversBar: () => j('/api/component/top-movers-bar'),
  gainers: () => j('/api/component/gainers-table'),
  losers: () => j('/api/component/losers-table'),
};

export const getJSON = async (path, opts = {}) => {
  const res = await fetch(path.startsWith('http') ? path : `${API_ORIGIN}${path}`, {
    headers: { Accept: 'application/json' },
    ...opts,
  });
  if (!res.ok) throw new Error(`HTTP ${res.status} ${res.statusText}`);
  return res.json();
};

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
