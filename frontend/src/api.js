

// API configuration for BHABIT CB4 with dynamic base URL and fallback
// Support special value 'relative' to use same-origin relative /api requests (works with Vercel rewrites)
const RAW_ENV_BASE = import.meta.env.VITE_API_URL;
// Runtime environment guards
const RUNTIME_IS_DEV = Boolean(import.meta.env && import.meta.env.DEV);
const RUNTIME_IS_LOCAL_HOST = (typeof window !== 'undefined') && ['localhost', '127.0.0.1', '0.0.0.0'].includes(window.location.hostname);
// Explicit opt-in for any localhost probing. Default: disabled everywhere.
const ENABLE_LOCAL_PROBE = String(import.meta.env?.VITE_ENABLE_LOCAL_PROBE || '').trim() === '1';

// More robust API_BASE_URL detection with multiple fallbacks
let API_BASE_URL;
if (RAW_ENV_BASE && RAW_ENV_BASE !== 'relative') {
  // If VITE_API_URL is set to any value (including '/api'), use it directly
  API_BASE_URL = RAW_ENV_BASE.trim();
} else if (RAW_ENV_BASE === 'relative') {
  API_BASE_URL = ''; // same-origin relative mode
} else {
  // Enhanced fallback: check multiple env var names
  const fallbackBase = (
    import.meta.env.PUBLIC_API_BASE ||
    import.meta.env.API_BASE_URL ||
    '' // default to relative base (no localhost)
  );
  API_BASE_URL = fallbackBase;
}
API_BASE_URL = API_BASE_URL.replace(/\/$/, '');

// Enhanced runtime debug output
console.info('[api.debug] RUNTIME_IS_DEV=%s RUNTIME_IS_LOCAL_HOST=%s ENABLE_LOCAL_PROBE=%s API_BASE_URL=%s RAW_ENV_BASE=%s',
  String(RUNTIME_IS_DEV), String(RUNTIME_IS_LOCAL_HOST), String(ENABLE_LOCAL_PROBE), String(API_BASE_URL), String(RAW_ENV_BASE));

const buildApiEndpoints = (base) => ({
  topBanner: `${base}/component/top-banner-scroll`,
  bottomBanner: `${base}/component/bottom-banner-scroll`,
  gainersTable: `${base}/component/gainers-table`,
  gainersTable1Min: `${base}/component/gainers-table-1min`,
  gainersTable3Min: `${base}/component/gainers-table-3min`,
  losersTable3Min: `${base}/component/losers-table-3min`,
  losersTable: `${base}/component/losers-table`,
  alertsRecent: `${base}/alerts/recent`,
  topMoversBar: `${base}/component/top-movers-bar`,
  crypto: `${base}/crypto`,
  health: `${base}/health`,
  serverInfo: `${base}/server-info`,
  metrics: `${base}/metrics`,
  marketOverview: `${base}/market-overview`,
  watchlistInsights: `${base}/watchlist/insights`,
  watchlistInsightsLog: `${base}/watchlist/insights/log`,
  watchlistInsightsPrice: `${base}/watchlist/insights/price`,
  technicalAnalysis: (symbol) => `${base}/technical-analysis/${symbol}`,
  cryptoNews: (symbol) => `${base}/news/${symbol}`,
  socialSentiment: (symbol) => `${base}/social-sentiment/${symbol}`,
  sentiment: (symbols) => `${base}/sentiment?symbols=${encodeURIComponent(symbols)}`,
  watchlist: `${base}/watchlist`,
  askCodex: `${base}/ask-codex`,
  learnLessons: `${base}/learn/lessons`,
  products: `${base}/products`,
});

// Use '/api' when using same-origin relative mode so we hit Backend routes consistently
const resolveBase = () => (API_BASE_URL === '' || API_BASE_URL === 'relative' ? '/api' : API_BASE_URL);
export const API_ENDPOINTS = buildApiEndpoints(resolveBase());

export const getApiBaseUrl = () => API_BASE_URL;
export const setApiBaseUrl = (url) => {
  if (!url) return;
  API_BASE_URL = url.replace(/\/$/, '');
  Object.assign(API_ENDPOINTS, buildApiEndpoints(resolveBase()));
  console.info('[api] Switched API base to', API_BASE_URL);
};

import { normalizeComponentPayload } from './services/normalize.js';

// Fetch data from API with throttling and automatic base fallback
export const fetchData = async (endpoint, fetchOptions = {}) => {
  try {
    const response = await fetch(endpoint, fetchOptions);
    if (response.ok) {
      const contentType = response.headers.get('content-type') || '';
      if (contentType.includes('application/json')) {
        return response.json();
      }
      return { ok: true, raw: await response.text() };
    }
    const text = await response.text().catch(() => '');
    throw new Error(`API Error: ${response.status} ${response.statusText} on ${endpoint}. ${text}`);
  } catch (error) {
    console.error('API fetch error:', error);
    throw error;
  }
};

export const fetchComponent = async (endpoint, fetchOptions = {}) => {
  const payload = await fetchData(endpoint, fetchOptions);
  return normalizeComponentPayload(payload);
};

// POST helper with the same dynamic fallback and timeouts as fetchData
export const postJson = async (endpoint, body = {}, fetchOptions = {}) => {
  return fetchData(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...(fetchOptions.headers || {}) },
      body: JSON.stringify(body),
      ...fetchOptions,
    });
};
