

// API configuration for BHABIT CB4 with a single, proxy-safe base URL
const resolveBase = () => {
  const raw =
    import.meta.env.VITE_API_BASE ||
    import.meta.env.VITE_API_BASE_URL ||
    import.meta.env.VITE_BACKEND_URL ||
    "";
  return String(raw).replace(/\/$/, "");
};

const joinUrl = (base, path) => {
  const b = String(base || '').replace(/\/+$/, '');
  const p = String(path || '');
  const normalized = p.startsWith('/') ? p : `/${p}`;
  return `${b}${normalized}`;
};

let API_BASE_URL = resolveBase();
let SENTIMENT_BASE_URL = API_BASE_URL;
const joinEndpoint = (path) => joinUrl(API_BASE_URL, path);

const buildEndpoints = () => ({
  data: joinEndpoint('/data'),
  topBanner: joinEndpoint('/api/banner-top'),
  bottomBanner: joinEndpoint('/api/banner-bottom'),
  askCodex: joinEndpoint('/api/ask-codex'),
  gainersTable: joinEndpoint('/api/component/gainers-table'),
  gainersTable1Min: joinEndpoint('/api/component/gainers-table-1min'),
  losersTable: joinEndpoint('/api/component/losers-table'),
  alertsRecent: joinEndpoint('/api/alerts/recent'),
  topMoversBar: joinEndpoint('/api/component/top-movers-bar'),
  crypto: joinEndpoint('/api/crypto'),
  health: joinEndpoint('/api/health'),
  serverInfo: joinEndpoint('/api/server-info'),
  watchlistInsightsLatest: joinEndpoint('/api/watchlist/insights/latest'),
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
export const getSentimentBaseUrl = () => SENTIMENT_BASE_URL;
export const setApiBaseUrl = (url) => {
  if (!url) return;
  API_BASE_URL = url.replace(/\/$/, '');
  SENTIMENT_BASE_URL = API_BASE_URL;
  API_ENDPOINTS = buildEndpoints();
  try { console.info('[api] Switched API base to', API_BASE_URL); } catch (_) {}
};

export async function fetchLatestAlerts(symbols = []) {
  if (!Array.isArray(symbols) || symbols.length === 0) return {};
  try {
    const res = await fetch(API_ENDPOINTS.watchlistInsightsLatest, {
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
    const status = response.status;
    throw new Error(`HTTP error! status: ${status}`);
  } catch (error) {
    console.error('API fetch error:', error);
    throw error;
  }
};

// Fetch consolidated dataset for dashboard consumers (fixed base + /data)
export async function fetchAllData({ signal } = {}) {
  const url = API_ENDPOINTS.data;
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
