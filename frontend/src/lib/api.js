export const API_BASE = import.meta.env?.VITE_API_BASE || '';

const normalise = (path) => {
  if (!path) return path;
  if (path.startsWith('http')) return path;
  if (path.startsWith('/')) return `${API_BASE}${path}`;
  return `${API_BASE}/${path}`;
};

export async function fetchJson(url, init = {}) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 9000);
  try {
    const res = await fetch(normalise(url), {
      credentials: 'same-origin',
      headers: { accept: 'application/json', ...(init.headers || {}) },
      ...init,
      signal: controller.signal,
    });
    if (!res.ok) {
      const text = await res.text().catch(() => '');
      const suffix = text ? ` :: ${text.slice(0, 180)}` : '';
      throw new Error(`HTTP ${res.status} ${res.statusText} @ ${url}${suffix}`);
    }
    return res.json();
  } finally {
    clearTimeout(timeoutId);
  }
}

export const httpGet = fetchJson;
export const fetchComponent = fetchJson;

export const endpoints = {
  health: normalise('/api/health'),
  gainers1m: normalise('/api/component/gainers-table-1min'),
  gainers3m: normalise('/api/component/gainers-table'),
  losers3m: normalise('/api/component/losers-table'),
  banner1h: normalise('/api/component/top-movers-bar'),
  bannerVolume1h: normalise('/api/component/banner-volume-1h'),
  topMoversBar: normalise('/api/component/top-movers-bar'),
  alertsRecent: (limit = 25) => normalise(`/api/alerts/recent?limit=${limit}`),
  metrics: normalise('/api/metrics'),
};

const coerceArray = (payload) => {
  if (Array.isArray(payload)) return payload;
  if (payload?.rows && Array.isArray(payload.rows)) return payload.rows;
  if (payload?.data && Array.isArray(payload.data)) return payload.data;
  return [];
};

export const mapRow = (row = {}) => {
  const symbol = String(row.ticker ?? row.symbol ?? row.product_id ?? '')
    .replace(/-USD$/i, '')
    .toUpperCase();
  const price = Number(row.last ?? row.current_price ?? row.price ?? 0);
  const changePctRaw =
    typeof row.changePct === 'number'
      ? row.changePct
      : typeof row.pct === 'number'
      ? row.pct
      : typeof row.price_change_percentage_1min === 'number'
      ? row.price_change_percentage_1min
      : typeof row.price_change_percentage_3min === 'number'
      ? row.price_change_percentage_3min
      : typeof row.change === 'number'
      ? row.change
      : 0;
  return {
    symbol,
    price,
    changePct: Number(changePctRaw) || 0,
  };
};

export const mapBanner = (row = {}) => {
  const symbol = String(row.symbol ?? row.ticker ?? '')
    .replace(/-USD$/i, '')
    .toUpperCase();
  const price = Number(row.price ?? row.last ?? row.current_price ?? 0);
  const pctRaw =
    typeof row.pct === 'number'
      ? row.pct
      : typeof row.changePct === 'number'
      ? row.changePct
      : typeof row.change === 'number'
      ? row.change
      : 0;
  return {
    symbol,
    price,
    pct: Number(pctRaw) || 0,
    label: row.label ?? row.tag ?? '',
  };
};

export const mapRows = (payload, transform = mapRow) => coerceArray(payload).map(transform);
export const mapBanners = (payload) => coerceArray(payload).map(mapBanner);

// ---- Watchlist helpers (localStorage-backed) -------------------------------

const WATCHLIST_KEY = 'watchlist';

export function getWatchlist() {
  try {
    const raw = localStorage.getItem(WATCHLIST_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function setWatchlist(nextList) {
  try {
    const arr = Array.isArray(nextList) ? nextList : [];
    localStorage.setItem(WATCHLIST_KEY, JSON.stringify(arr));
    return arr;
  } catch {
    return [];
  }
}

export function addToWatchlist(symbol) {
  const s = (symbol || '').toUpperCase().trim();
  if (!s) return getWatchlist();
  const list = getWatchlist();
  if (!list.includes(s)) list.push(s);
  return setWatchlist(list);
}

export function removeFromWatchlist(symbol) {
  const s = (symbol || '').toUpperCase().trim();
  const list = getWatchlist().filter((x) => x !== s);
  return setWatchlist(list);
}
