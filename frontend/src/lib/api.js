const rawBase = import.meta.env?.VITE_API_URL ?? "";
const trimmedBase = typeof rawBase === "string" ? rawBase.trim() : "";
// Normalize API base: empty or 'relative' means no injected base.
let API_BASE = trimmedBase && trimmedBase !== "relative" ? trimmedBase.replace(/\/$/, "") : "";
// If someone set VITE_API_URL to include a trailing '/api', strip it so we don't
// accidentally produce '/api/api' when joining with paths that start with /api.
if (API_BASE && API_BASE.endsWith('/api')) {
  API_BASE = API_BASE.replace(/\/api\/*$/, '');
}

if (typeof window !== "undefined") {
  window.__API_BASE__ = API_BASE;
}

const joinUrl = (base, path) => {
  // base may be empty -> return path as-is
  if (!path) return path || '';
  if (path.startsWith('http')) return path;

  // If base looks like an absolute URL (has protocol://), prefer URL resolution
  // which preserves the protocol slashes instead of collapsing them.
  try {
    if (base && /^(https?:)?\/\//i.test(base)) {
      // new URL(path, base) handles leading/trailing slashes correctly
      return new URL(path, base).toString();
    }
  } catch (e) {
    // fall through to safe string join
  }

  const b = (base || '').replace(/\/+$/, '');
  const p = path.replace(/^\/+/, '');
  if (!b) return `/${p}`.replace(/\/+/g, '/');
  return `${b}/${p}`.replace(/\/+/g, '/');
};

function normalizeApiPath(path) {
  if (!path) return '/api';
  // allow direct /data passthrough: callers may explicitly want the /data
  // aggregate endpoint instead of the legacy /api/component/... routes.
  if (typeof path === 'string' && path.startsWith('/data')) return path;
  if (!path) return '/api';
  let p = typeof path === 'string' ? path : String(path);
  if (!p.startsWith('/')) p = `/${p}`;
  // Collapse repeated leading /api segments: '/api/api/...', '/api/api/api/...' => '/api/...'
  p = p.replace(/^\/(?:api\/)+/, '/api/');
  // Ensure it begins with /api
  if (!p.startsWith('/api')) {
    // avoid producing '/api//' for root
    p = p === '/' ? '/api' : `/api${p}`;
  }
  return p;
}

const normalise = (path) => {
  // If caller passed an absolute URL (eg. 'http://...'), return it unchanged.
  // This avoids producing '/api/http://...' when callers accidentally pass
  // fully-qualified endpoints into helpers that expect a path.
  if (typeof path === 'string' && /^(https?:)?\/\//i.test(path)) {
    return path;
  }
  return joinUrl(API_BASE, normalizeApiPath(path));
};

// If the app is being served from a different origin (eg. static build on 5174)
// and an absolute VITE_API_URL is provided, rewrite any browser fetch() calls
// that use relative paths beginning with '/api/' to point at the API base.
if (typeof window !== 'undefined' && API_BASE) {
  try {
    const apiOrigin = new URL(API_BASE).origin;
    const pageOrigin = window.location.origin;
    if (apiOrigin !== pageOrigin) {
      const _nativeFetch = window.fetch.bind(window);
      window.fetch = async (input, init) => {
        try {
          let url = input;
          // Handle Request objects
          if (input && typeof input === 'object' && input.url) {
            url = input.url;
          }
          if (typeof url === 'string' && url.startsWith('/api/')) {
            url = joinUrl(API_BASE, url);
            // If original input was a Request, clone it pointing to new url
            if (input && typeof input === 'object' && input.url) {
              input = new Request(url, input);
            } else {
              input = url;
            }
          }
          return _nativeFetch(input, init);
        } catch (e) {
          return _nativeFetch(input, init);
        }
      };
    }
  } catch (e) {
    // ignore
  }
}

export const endpoints = {
  // point everything at the single /data aggregate endpoint the backend currently provides
  banner1h: '/data',
  bannerVolume1h: '/data',
  gainers1m: '/data',
  gainers3m: '/data',
  losers3m: '/data',
  vol1h: '/data',
  health: '/data',
  topMoversBar: '/data',
  alertsRecent: (limit = 25) => `/data?limit=${limit}`,
  metrics: '/data',
};

export async function fetchJson(url, init = {}, ms = 9000) {
  const hasExternalSignal = Boolean(init && init.signal);
  let controller;
  let timeoutId;
  if (!hasExternalSignal) {
    controller = new AbortController();
    timeoutId = setTimeout(() => controller.abort(), ms);
  }
  try {
    const target = normalise(url);
    const res = await fetch(target, {
      credentials: init.credentials ?? "same-origin",
      headers: {
        accept: "application/json",
        ...(init.headers || {}),
      },
      ...init,
      signal: hasExternalSignal ? init.signal : controller.signal,
    });
    if (!res.ok) {
      const text = await res.text().catch(() => "");
      const suffix = text ? ` :: ${text.slice(0, 180)}` : "";
      throw new Error(`HTTP ${res.status} ${res.statusText} @ ${target}${suffix}`);
    }
    return res.json();
  } finally {
    if (timeoutId) clearTimeout(timeoutId);
  }
}

export async function getJSON(path) {
  return fetchJson(path);
}

export const httpGet = fetchJson;
export const fetchComponent = fetchJson;

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
  // Preserve original fields (like initial_price_1min / initial_price_3min)
  // while providing normalized properties the UI expects.
  return {
    ...row,
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
