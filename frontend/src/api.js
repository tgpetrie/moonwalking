

// API configuration for BHABIT CB4 with dynamic base URL and fallback
const DEFAULT_API_BASE = (
  import.meta.env.VITE_API_BASE_URL ||
  import.meta.env.VITE_BACKEND_URL ||
  'http://127.0.0.1:5003' // sane local default; avoid random/stale ports
).replace(/\/$/, '');

const joinUrl = (base, path) => {
  const b = String(base || '').replace(/\/+$/, '');
  const p = String(path || '');
  const normalized = p.startsWith('/') ? p : `/${p}`;
  return `${b}${normalized}`;
};

let API_BASE_URL = DEFAULT_API_BASE;
const joinEndpoint = (path) => joinUrl(API_BASE_URL, path);

const buildEndpoints = () => ({
  topBanner: joinEndpoint('/api/component/top-banner-scroll'),
  bottomBanner: joinEndpoint('/api/component/bottom-banner-scroll'),
  gainersTable: joinEndpoint('/api/component/gainers-table'),
  gainersTable1Min: joinEndpoint('/api/component/gainers-table-1min'),
  losersTable: joinEndpoint('/api/component/losers-table'),
  alertsRecent: joinEndpoint('/api/alerts/recent'),
  topMoversBar: joinEndpoint('/api/component/top-movers-bar'),
  crypto: joinEndpoint('/api/crypto'),
  health: joinEndpoint('/api/health'),
  serverInfo: joinEndpoint('/api/server-info'),
  marketOverview: joinEndpoint('/api/market-overview'),
  watchlistInsights: joinEndpoint('/api/watchlist/insights'),
  watchlistInsightsLog: joinEndpoint('/api/watchlist/insights/log'),
  watchlistInsightsPrice: joinEndpoint('/api/watchlist/insights/price'),
  technicalAnalysis: (symbol) => joinEndpoint(`/api/technical-analysis/${symbol}`),
  cryptoNews: (symbol) => joinEndpoint(`/api/news/${symbol}`),
  socialSentiment: (symbol) => joinEndpoint(`/api/social-sentiment/${symbol}`)
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
    const res = await fetch(joinEndpoint('/api/watchlist/insights/latest'), {
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
const CACHE_DURATION = 10000; // 10 seconds

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
  // Keep this tight: avoid “port rot” to old dev ports.
  'http://localhost:5003', 'http://127.0.0.1:5003'
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

// Fetch consolidated dataset for dashboard consumers (fixed base + /data)
export async function fetchAllData({ signal } = {}) {
  const apiBase = (
    import.meta?.env?.VITE_API_BASE_URL ||
    API_BASE_URL
  );

  const url = joinUrl(apiBase, '/data');
  const res = await fetch(url, {
    signal,
    headers: { Accept: 'application/json' },
    cache: 'no-store'
  });

  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`fetchAllData failed ${res.status}: ${text || res.statusText}`);
  }

  return res.json();
}


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
