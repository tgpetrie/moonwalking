// API configuration for BHABIT CB4 with dynamic base URL and fallback
// Support special value 'relative' to use same-origin relative /api requests (works with Vercel rewrites)
const RAW_ENV_BASE = import.meta.env.VITE_API_URL;
let API_BASE_URL;
if (RAW_ENV_BASE && RAW_ENV_BASE !== 'relative') {
  API_BASE_URL = RAW_ENV_BASE.trim();
} else if (RAW_ENV_BASE === 'relative') {
  API_BASE_URL = ''; // same-origin relative mode
} else {
  API_BASE_URL = 'http://localhost:5001'; // dev fallback
}
API_BASE_URL = API_BASE_URL.replace(/\/$/, '');

const buildEndpoints = () => ({
  topBanner: `${API_BASE_URL}/api/component/top-banner-scroll`,
  bottomBanner: `${API_BASE_URL}/api/component/bottom-banner-scroll`,
  gainersTable: `${API_BASE_URL}/api/component/gainers-table`,
  gainersTable1Min: `${API_BASE_URL}/api/component/gainers-table-1min`,
  losersTable: `${API_BASE_URL}/api/component/losers-table`,
  alertsRecent: `${API_BASE_URL}/api/alerts/recent`,
  topMoversBar: `${API_BASE_URL}/api/component/top-movers-bar`,
  crypto: `${API_BASE_URL}/api/crypto`,
  health: `${API_BASE_URL}/api/health`,
  serverInfo: `${API_BASE_URL}/api/server-info`,
  marketOverview: `${API_BASE_URL}/api/market-overview`,
  watchlistInsights: `${API_BASE_URL}/api/watchlist/insights`,
  watchlistInsightsLog: `${API_BASE_URL}/api/watchlist/insights/log`,
  watchlistInsightsPrice: `${API_BASE_URL}/api/watchlist/insights/price`,
  technicalAnalysis: (symbol) => `${API_BASE_URL}/api/technical-analysis/${symbol}`,
  cryptoNews: (symbol) => `${API_BASE_URL}/api/news/${symbol}`,
  socialSentiment: (symbol) => `${API_BASE_URL}/api/social-sentiment/${symbol}`
});

export let API_ENDPOINTS = buildEndpoints();

// In production (Cloudflare Pages), proxy /api/* via Functions, so relative routing is fine
// Env var provided only in CF Pages Functions
export const API_BASE = typeof import.meta.env.PUBLIC_API_BASE_URL === 'string'
  ? import.meta.env.PUBLIC_API_BASE_URL
  : API_BASE_URL;

export const getApiBaseUrl = () => API_BASE_URL;

export const setApiBaseUrl = (url) => {
  if (!url) return;
  API_BASE_URL = url.replace(/\/$/, '');
  API_ENDPOINTS = buildEndpoints();
  try { console.info('[api] Switched API base to', API_BASE_URL); } catch (_) {}
};

export async function fetchLatestAlerts(symbols = []) {
  if (!Array.isArray(symbols) || symbols.length === 0) return {};
  try {
    const res = await fetch(`${API_BASE_URL}/api/watchlist/insights/latest`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbols })
    });
    if (!res.ok) return {};
    const data = await res.json();
    return data.latest || {};
  } catch (e) {
    console.error('fetchLatestAlerts error', e);
    return {};
  }
}

// Request throttling to prevent resource exhaustion
const requestCache = new Map();
// add in-flight dedupe map and per-route TTLs
const inflight = new Map();

export const CACHE_DURATION_1MIN = 3000;
const TTL = {
  "/api/alerts/recent": 5000,
  "/api/component/gainers-table-1min": CACHE_DURATION_1MIN,
  "/api/component/gainers-table": 10000,
  "/api/component/losers-table": 10000,
  "/api/component/top-banner-scroll": 15000,
  "/api/component/bottom-banner-scroll": 15000,
  default: 8000
};

// ±12% jitter to avoid thundering herds
const JITTER_FRAC = 0.12;
const withJitter = (ms, frac = JITTER_FRAC) => {
  const delta = ms * frac;
  return Math.max(500, Math.round(ms + (Math.random() * 2 - 1) * delta));
};

function ttlFor(url) {
  for (const k of Object.keys(TTL)) if (k !== 'default' && url.includes(k)) return TTL[k];
  return TTL.default;
}

// Optional: only show custom-defined alerts (enable with VITE_ALERTS_CUSTOM_ONLY=1)
const ALERTS_CUSTOM_ONLY = (() => {
  const v = String(import.meta.env.VITE_ALERTS_CUSTOM_ONLY ?? "").toLowerCase();
  return v === "1" || v === "true" || v === "yes";
})();

// If enabled, filter /api/alerts/recent payloads down to "custom" alerts only
// Supports a few common shapes: array, {items:[]}, or {alerts:[]}
const maybeFilterCustomAlerts = (endpoint, data) => {
  try {
    if (!ALERTS_CUSTOM_ONLY) return data;
    if (!/\/api\/alerts\/recent(?:\b|\/|\?)/.test(endpoint)) return data;

    const arr = Array.isArray(data)
      ? data
      : (Array.isArray(data.items) ? data.items
        : (Array.isArray(data.alerts) ? data.alerts : null));

    if (!arr) return data;

    const filtered = arr.filter((a) =>
      (a && a.custom === true) ||
      (a && a.kind === "custom") ||
      (a && a.source === "custom") ||
      (Array.isArray(a?.tags) && a.tags.includes("custom"))
    );

    if (Array.isArray(data)) return filtered;
    if (Array.isArray(data.items)) return { ...data, items: filtered };
    if (Array.isArray(data.alerts)) return { ...data, alerts: filtered };
    return data;
  } catch {
    return data;
  }
};

// Internal: probe a candidate base URL via /api/health with a short timeout
const probeBase = async (baseUrl, timeoutMs = 1500) => {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    // Prefer server-info which should return 200 regardless of external API status
    const res = await fetch(`${baseUrl.replace(/\/$/, '')}/api/server-info`, { signal: controller.signal });
    return res.ok;
  } catch {
    return false;
  } finally {
    clearTimeout(timer);
  }
};

const CANDIDATE_BASES = [
  'http://localhost:5001','http://127.0.0.1:5001',
  'http://localhost:5002','http://127.0.0.1:5002',
  'http://localhost:5003','http://127.0.0.1:5003',
  'http://localhost:5004','http://127.0.0.1:5004',
  'http://localhost:5005','http://127.0.0.1:5005',
  'http://localhost:5006','http://127.0.0.1:5006',
  'http://localhost:5007','http://127.0.0.1:5007',
  'http://localhost:5008','http://127.0.0.1:5008',
  'http://localhost:5009','http://127.0.0.1:5009'
];

// Fetch data from API with throttling and automatic base fallback
export const fetchData = async (endpoint, fetchOptions = {}) => {
  const now = Date.now();
  const baseTtl = ttlFor(endpoint);
  // For gainers-table-1min, prefer the short fixed cache value (no extra jitter)
  const cacheTtl = endpoint.includes('/gainers-table-1min') ? baseTtl : withJitter(baseTtl);
  const cached = requestCache.get(endpoint);
  if (cached && now < cached.expiresAt) {
    return cached.data;
  }
  // de-dupe in-flight requests
  if (inflight.has(endpoint)) {
    return inflight.get(endpoint);
  }
  const controller = new AbortController();
  const p = (async () => {
    try {
      const res = await fetch(endpoint, { ...fetchOptions, signal: controller.signal });
      if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
      const raw = await res.json();
      const data = maybeFilterCustomAlerts ? maybeFilterCustomAlerts(endpoint, raw) : raw;
      const expiresAt = Date.now() + cacheTtl;
      requestCache.set(endpoint, { data, expiresAt });
      return data;
    } finally {
      inflight.delete(endpoint);
    }
  })();
  inflight.set(endpoint, p);
  return p;
};

// SWR fetcher for useSWR hooks
// SWR may call the fetcher with a key array (e.g. [endpoint, someTrigger]).
// Accept either a string or an array and use the first element as the endpoint.
export const swrFetcher = (key) => {
  const endpoint = Array.isArray(key) ? key[0] : key;
  return fetchData(endpoint);
};

// Backwards-compatible alias: some components import `fetchWithSWR` from `src/api`.
// Provide a thin alias to the existing `swrFetcher` to avoid build-time import errors.
export const fetchWithSWR = swrFetcher;

// --- Local Storage Watchlist Functions ---
const WATCHLIST_KEY = 'crypto_watchlist';

export async function getWatchlist() {
  try {
    const raw = localStorage.getItem(WATCHLIST_KEY);
    if (!raw) return [];
    return JSON.parse(raw);
  } catch (e) {
    console.error('LocalStorage getWatchlist error:', e);
    return [];
  }
}

export async function addToWatchlist(symbol, price = null) {
  try {
    let list = await getWatchlist();
    // Check if symbol already exists (handle both string and object formats)
    const existingItem = list.find(item =>
      typeof item === 'string' ? item === symbol : item.symbol === symbol
    );
    
    if (!existingItem) {
      // Add as object with price info
      const newItem = { 
        symbol, 
        priceAtAdd: price || Math.random() * 1000 // fallback random price if not provided
      };
      list.push(newItem);
      localStorage.setItem(WATCHLIST_KEY, JSON.stringify(list));
    }
    return list;
  } catch (e) {
    console.error('LocalStorage addToWatchlist error:', e);
    return await getWatchlist();
  }
}

export async function removeFromWatchlist(symbol) {
  try {
    let list = await getWatchlist();
    // Filter by symbol (handle both string and object formats)
    list = list.filter(item => 
      typeof item === 'string' ? item !== symbol : item.symbol !== symbol
    );
    localStorage.setItem(WATCHLIST_KEY, JSON.stringify(list));
    return list;
  } catch (e) {
    console.error('LocalStorage removeFromWatchlist error:', e);
    return await getWatchlist();
  }
}
