

// API configuration for BHABIT CB4 with dynamic base URL and fallback
// Support special value 'relative' to use same-origin relative /api requests (works with Vercel rewrites)
const RAW_ENV_BASE = import.meta.env.VITE_API_URL;
let API_BASE_URL;
if (RAW_ENV_BASE && RAW_ENV_BASE !== 'relative' && !/^\s*\/api(\/|$)/.test(RAW_ENV_BASE)) {
  API_BASE_URL = RAW_ENV_BASE.trim();
} else if (RAW_ENV_BASE === 'relative') {
  API_BASE_URL = ''; // same-origin relative mode
} else if (/^\s*\/api(\/|$)/.test(RAW_ENV_BASE || '')) {
  // If VITE_API_URL is '/api' or '/api/...', treat as same-origin relative
  API_BASE_URL = '';
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
  metrics: `${API_BASE_URL}/api/metrics`,
  marketOverview: `${API_BASE_URL}/api/market-overview`,
  watchlistInsights: `${API_BASE_URL}/api/watchlist/insights`,
  watchlistInsightsLog: `${API_BASE_URL}/api/watchlist/insights/log`,
  watchlistInsightsPrice: `${API_BASE_URL}/api/watchlist/insights/price`,
  technicalAnalysis: (symbol) => `${API_BASE_URL}/api/technical-analysis/${symbol}`,
  cryptoNews: (symbol) => `${API_BASE_URL}/api/news/${symbol}`,
  socialSentiment: (symbol) => `${API_BASE_URL}/api/social-sentiment/${symbol}`
});

export let API_ENDPOINTS = buildEndpoints();
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

import { isMobileDevice, getMobileOptimizedConfig } from './utils/mobileDetection.js';

// Request throttling to prevent resource exhaustion
const requestCache = new Map();
const mobileConfig = getMobileOptimizedConfig();
const CACHE_DURATION = mobileConfig.cacheDuration; // Mobile-optimized cache duration

// Internal: probe a candidate base URL via /api/health with a mobile-optimized timeout
const probeBase = async (baseUrl, timeoutMs = null) => {
  const defaultTimeout = timeoutMs || (isMobileDevice() ? mobileConfig.fetchTimeout : 1500);
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), defaultTimeout);
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
  'http://localhost:5001', 'http://127.0.0.1:5001',
  'http://localhost:5002', 'http://127.0.0.1:5002',
  'http://localhost:5003', 'http://127.0.0.1:5003',
  'http://localhost:5004', 'http://127.0.0.1:5004',
  'http://localhost:5005', 'http://127.0.0.1:5005',
  'http://localhost:5006', 'http://127.0.0.1:5006',
  'http://localhost:5007', 'http://127.0.0.1:5007'
];

// Fetch data from API with throttling and automatic base fallback
export const fetchData = async (endpoint, fetchOptions = {}) => {
  try {
    // Check cache first to avoid duplicate requests
    const now = Date.now();
    const cached = requestCache.get(endpoint);
    if (cached && (now - cached.timestamp) < CACHE_DURATION) {
      return cached.data;
    }
    const response = await fetch(endpoint, fetchOptions);
    if (response.ok) {
      const data = await response.json();
      requestCache.set(endpoint, { data, timestamp: now });
      return data;
    }
    // Non-OK response: attempt fallback only for likely wrong-host cases (404/502/503)
    const status = response.status;
    if ([404, 502, 503, 504].includes(status)) {
      throw new Error(`HTTP error! status: ${status}`);
    }
    throw new Error(`HTTP error! status: ${status}`);
  } catch (error) {
    // Attempt dynamic base fallback on network errors or wrong-host statuses
    try {
      const oldBase = API_BASE_URL;
      const altBases = CANDIDATE_BASES.filter(b => b.replace(/\/$/, '') !== oldBase.replace(/\/$/, ''));
      for (const base of altBases) {
        const ok = await probeBase(base);
        if (!ok) continue;
        // Rebuild the endpoint using the probed base (don't switch global base until confirmed OK)
        let path = endpoint;
        if (endpoint.startsWith(oldBase)) {
          path = endpoint.substring(oldBase.length);
        } else {
          try {
            const u = new URL(endpoint);
            path = u.pathname + (u.search || '');
          } catch (_) {}
        }
        const newEndpoint = `${base.replace(/\/$/, '')}${path}`;
        const retryRes = await fetch(newEndpoint, fetchOptions);
        if (retryRes.ok) {
          // Commit base change only after endpoint success
          setApiBaseUrl(base);
          const data = await retryRes.json();
          requestCache.set(newEndpoint, { data, timestamp: Date.now() });
          return data;
        }
      }
    } catch (fallbackErr) {
      // swallow to rethrow original error below
    }
    console.error('API fetch error:', error);
    throw error;
  }
};


// --- Local Storage Watchlist Functions ---
// Store watchlist as an array of objects: { symbol, priceAtAdd, addedAt }
// Backwards-compatible: reads legacy arrays of strings and upgrades them in memory
const WATCHLIST_KEY = 'crypto_watchlist';

export async function getWatchlist() {
  try {
    const raw = localStorage.getItem(WATCHLIST_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    // Normalize to objects
    const normalized = parsed
      .map((item) => {
        if (typeof item === 'string') {
          return { symbol: item, priceAtAdd: 0, addedAt: 0 };
        }
        if (item && typeof item === 'object' && item.symbol) {
          return {
            symbol: item.symbol,
            priceAtAdd: Number(item.priceAtAdd) || 0,
            addedAt: Number(item.addedAt) || 0,
          };
        }
        return null;
      })
      .filter(Boolean);
    return normalized;
  } catch (e) {
    console.error('LocalStorage getWatchlist error:', e);
    return [];
  }
}

export async function addToWatchlist(symbol, priceAtAdd = null) {
  try {
    const list = await getWatchlist();
    const exists = list.some((it) => it && it.symbol === symbol);
    if (!exists) {
      const entry = {
        symbol,
        priceAtAdd: Number(priceAtAdd) || 0,
        addedAt: Date.now(),
      };
      const next = [...list, entry];
      localStorage.setItem(WATCHLIST_KEY, JSON.stringify(next));
      return next;
    }
    return list;
  } catch (e) {
    console.error('LocalStorage addToWatchlist error:', e);
    return await getWatchlist();
  }
}

export async function removeFromWatchlist(symbol) {
  try {
    const list = await getWatchlist();
    const next = list.filter((it) => it && it.symbol !== symbol);
    localStorage.setItem(WATCHLIST_KEY, JSON.stringify(next));
    return next;
  } catch (e) {
    console.error('LocalStorage removeFromWatchlist error:', e);
    return await getWatchlist();
  }
}
