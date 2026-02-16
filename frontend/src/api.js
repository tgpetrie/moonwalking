
import {
  getBackendBase,
  getBackendCandidates,
  normalizeBase,
  sanitizeBase,
  safeFetch,
} from "./config/api.js";

// API configuration for BHABIT CB4 with dynamic base URL and fallback
let API_BASE_URL = getBackendBase();
const encodeSymbol = (symbol) => encodeURIComponent(String(symbol || '').trim().toUpperCase());
const buildEndpoints = () => ({
  data: `${API_BASE_URL}/data`,
  topBanner: `${API_BASE_URL}/api/component/top-banner-scroll`,
  bottomBanner: `${API_BASE_URL}/api/component/bottom-banner-scroll`,
  gainersTable: `${API_BASE_URL}/api/component/gainers-table`,
  gainersTable3Min: `${API_BASE_URL}/api/component/gainers-table`,
  gainersTable1Min: `${API_BASE_URL}/api/component/gainers-table-1min`,
  losersTable: `${API_BASE_URL}/api/component/losers-table`,
  losersTable3Min: `${API_BASE_URL}/api/component/losers-table`,
  alertsRecent: `${API_BASE_URL}/api/alerts/recent`,
  topMoversBar: `${API_BASE_URL}/api/component/top-movers-bar`,
  crypto: `${API_BASE_URL}/api/crypto`,
  health: `${API_BASE_URL}/api/health`,
  serverInfo: `${API_BASE_URL}/api/server-info`,
  marketOverview: `${API_BASE_URL}/api/market-overview`,
  watchlistInsights: `${API_BASE_URL}/api/watchlist/insights`,
  watchlistInsightsLog: `${API_BASE_URL}/api/watchlist/insights/log`,
  watchlistInsightsPrice: `${API_BASE_URL}/api/watchlist/insights/price`,
  sentimentLatest: `${API_BASE_URL}/api/sentiment/latest`,
  sentiment: (symbol) => `${API_BASE_URL}/api/sentiment/latest${symbol ? `?symbol=${encodeSymbol(symbol)}` : ''}`,
  intelligenceReport: (symbol) => `${API_BASE_URL}/api/intelligence-report/${encodeSymbol(symbol)}`,
  insights: (symbol) => `${API_BASE_URL}/api/insights/${encodeSymbol(symbol)}`,
  coinHistory: (symbol) => `${API_BASE_URL}/api/insights/${encodeSymbol(symbol)}`,
  coinHistoryCb: (symbol) => `${API_BASE_URL}/api/insights/${encodeSymbol(symbol)}`,
  coinIntel: (symbol) => `${API_BASE_URL}/api/coin-intel?symbol=${encodeSymbol(symbol)}`,
  coinAlerts: (symbol) => `${API_BASE_URL}/api/coin-alerts?symbol=${encodeSymbol(symbol)}`,
  technicalAnalysis: (symbol) => `${API_BASE_URL}/api/technical-analysis/${symbol}`,
  cryptoNews: (symbol) => `${API_BASE_URL}/api/news/${symbol}`,
  socialSentiment: (symbol) => `${API_BASE_URL}/api/social-sentiment/${symbol}`
});

export let API_ENDPOINTS = buildEndpoints();
export const getApiBaseUrl = () => API_BASE_URL;
export const getSentimentBaseUrl = () => (
  import.meta.env.VITE_SENTIMENT_BASE_URL ||
  import.meta.env.VITE_SENTIMENT_URL ||
  import.meta.env.VITE_API_URL ||
  import.meta.env.VITE_API_BASE_URL ||
  ""
);
export const setApiBaseUrl = (url) => {
  const nextBase = sanitizeBase(url);
  if (!nextBase) return;
  API_BASE_URL = nextBase;
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

    // JSON safety: check content-type before parsing
    const contentType = res.headers.get("content-type") || "";
    if (!contentType.includes("application/json")) {
      console.warn('[fetchLatestAlerts] Non-JSON response:', contentType);
      return {};
    }

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

// Get candidate bases from config (no 8001, no port hunting)
const getCandidateBases = () => getBackendCandidates();

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
      // JSON safety: check content-type before parsing
      const contentType = response.headers.get("content-type") || "";
      if (!contentType.includes("application/json")) {
        console.warn('[fetchData] Non-JSON response:', { endpoint, contentType });
        throw new Error(`Expected JSON, got ${contentType}`);
      }

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
    if (error?.name === 'AbortError') {
      throw error;
    }
    // Attempt dynamic base fallback on network errors or wrong-host statuses
    try {
      const oldBase = API_BASE_URL;
      const altBases = getCandidateBases().filter(b => normalizeBase(b) !== normalizeBase(oldBase));
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
        const newEndpoint = `${normalizeBase(base)}${path}`;
        const retryRes = await fetch(newEndpoint, fetchOptions);
        if (retryRes.ok) {
          // JSON safety: check content-type before parsing
          const contentType = retryRes.headers.get("content-type") || "";
          if (!contentType.includes("application/json")) {
            console.warn('[fetchData retry] Non-JSON response:', { newEndpoint, contentType });
            continue; // Try next base
          }

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
    if (error?.name !== 'AbortError') {
      console.error('API fetch error:', error);
    }
    throw error;
  }
};


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
