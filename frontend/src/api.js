
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
  riskLevels: (symbol) => `${API_BASE_URL}/api/risk-levels/${encodeSymbol(symbol)}`,
  technicalAnalysis: (symbol) => `${API_BASE_URL}/api/technical-analysis/${symbol}`,
  cryptoNews: (symbol) => `${API_BASE_URL}/api/news/${symbol}`,
  socialSentiment: (symbol) => `${API_BASE_URL}/api/social-sentiment/${symbol}`,
  chartRead: (symbol, eventContext = null, horizon = null) => {
    const base = `${API_BASE_URL}/api/chart-read/${encodeSymbol(symbol)}`;
    const params = new URLSearchParams();
    const ctx = eventContext && typeof eventContext === "object" ? eventContext : null;
    const evidence = ctx?.evidence && typeof ctx.evidence === "object" ? ctx.evidence : {};
    const typeKey = String(ctx?.type_key || ctx?.type || "").trim().toUpperCase();
    const window = String(evidence.window || ctx?.window || "").trim();
    const asNumber = (value) => {
      if (value === "" || value === null || value === undefined) return null;
      const n = Number(value);
      return Number.isFinite(n) ? n : null;
    };
    const price = asNumber(evidence.price ?? ctx?.price);
    const pct = asNumber(evidence.pct ?? ctx?.pct);

    if (typeKey) params.set("event_type", typeKey);
    if (window) params.set("event_window", window);
    if (price !== null) params.set("event_price", String(price));
    if (pct !== null) params.set("event_pct", String(pct));
    // "swing" is the server default; only the other views need the parameter.
    if (horizon && horizon !== "swing") params.set("horizon", String(horizon));

    const query = params.toString();
    return query ? `${base}?${query}` : base;
  },
  // Industry liquidity stage, breadth and cycle buckets. `symbols` adds the
  // caller's watchlist to the scanned universe.
  macroCycleScan: (symbols = []) => {
    const base = `${API_BASE_URL}/api/macro-cycle-scan`;
    const list = normalizeScanSymbols(symbols);
    return list.length ? `${base}?symbols=${list.join(",")}` : base;
  }
});

// The server accepts at most 30 extra symbols; sorting keeps the URL (and so
// the request cache key) stable when a watchlist is merely reordered.
const MACRO_SCAN_MAX_SYMBOLS = 30;
export function normalizeScanSymbols(symbols) {
  const out = [];
  for (const raw of Array.isArray(symbols) ? symbols : []) {
    const sym = String(raw?.symbol ?? raw ?? "").trim().toUpperCase().replace(/-USD$/, "");
    if (/^[A-Z0-9]{1,15}$/.test(sym) && !out.includes(sym)) out.push(sym);
  }
  return out.sort().slice(0, MACRO_SCAN_MAX_SYMBOLS);
}

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


/**
 * GET /api/macro-cycle-scan: the industry liquidity stage, universe breadth
 * and the four ranked cycle buckets.
 *
 * The first call after a server restart answers `status: "warming"` with no
 * industry read while daily histories load; call again for the result. A
 * later call can answer `status: "refreshing"` with the previous scan.
 * Display context only: the payload says `blocks_alerts: false` and
 * `outcome_validated: false`.
 */
export async function fetchMacroCycleScan(symbols = [], fetchOptions = {}) {
  const payload = await fetchData(API_ENDPOINTS.macroCycleScan(symbols), fetchOptions);
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new Error("Unexpected macro cycle scan response");
  }
  return payload;
}

// --- Owner-only agent controls (credentialed, never cached) ---

async function ownerRequest(path, { method = "GET", body } = {}) {
  const init = { method, credentials: "include", cache: "no-store" };
  if (body !== undefined) {
    init.headers = { "Content-Type": "application/json" };
    init.body = JSON.stringify(body);
  }
  const res = await fetch(`${getBackendBase()}${path}`, init);
  const payload = await res.json().catch(() => ({}));
  if (!res.ok || payload?.status !== "live") {
    const error = new Error(payload?.error || `Request failed (${res.status})`);
    error.status = res.status;
    throw error;
  }
  return payload;
}

const proposalPath = (id, decision) =>
  `/api/agents/proposals/${encodeURIComponent(id)}/${decision}`;

/** GET /api/agents/proposals → { proposals, autonomy }. Dry-run only. */
export function fetchAgentProposals({ status, symbol, limit } = {}) {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  if (symbol) params.set("symbol", symbol);
  if (limit) params.set("limit", String(limit));
  const query = params.toString();
  return ownerRequest(`/api/agents/proposals${query ? `?${query}` : ""}`);
}

/** Records approval only; the backend never places an order on approval. */
export const approveAgentProposal = (id) =>
  ownerRequest(proposalPath(id, "approve"), { method: "POST", body: {} });

export const rejectAgentProposal = (id) =>
  ownerRequest(proposalPath(id, "reject"), { method: "POST", body: {} });

export const fetchAgentAutonomy = () => ownerRequest("/api/agents/autonomy");

/**
 * POST /api/agents/run-cycle-pass → { status: "ok" | "skipped", reason,
 * proposals, compounding_summary, cycle_scan }. Runs the Cycle Strategist and
 * the smart alerts once on the server. Dry-run only: no order is placed.
 */
export async function runCycleAgentPass() {
  const res = await fetch(`${getBackendBase()}/api/agents/run-cycle-pass`, {
    method: "POST",
    credentials: "include",
    cache: "no-store",
    headers: { "Content-Type": "application/json" },
    body: "{}",
  });
  const payload = await res.json().catch(() => ({}));
  if (!res.ok || !["ok", "skipped"].includes(payload?.status)) {
    const error = new Error(payload?.error || `Request failed (${res.status})`);
    error.status = res.status;
    throw error;
  }
  return payload;
}

/** changes: any of autonomy_mode, execution_mode, emergency_pause, daily_order_cap. */
export const updateAgentAutonomy = (changes) =>
  ownerRequest("/api/agents/autonomy", { method: "POST", body: changes });

export const fetchSmartAlertRules = () => ownerRequest("/api/smart-alerts/rules");

export const createSmartAlertRule = (rule) =>
  ownerRequest("/api/smart-alerts/rules", { method: "POST", body: rule });

export const updateSmartAlertRule = (ruleId, changes) =>
  ownerRequest(`/api/smart-alerts/rules/${Number(ruleId)}`, { method: "PATCH", body: changes });

export const deleteSmartAlertRule = (ruleId) =>
  ownerRequest(`/api/smart-alerts/rules/${Number(ruleId)}`, { method: "DELETE" });

export function fetchSmartAlertHistory({ limit, symbol } = {}) {
  const params = new URLSearchParams();
  if (limit) params.set("limit", String(limit));
  if (symbol) params.set("symbol", symbol);
  const query = params.toString();
  return ownerRequest(`/api/smart-alerts/history${query ? `?${query}` : ""}`);
}

/** Fires one test alert immediately (ignores quiet hours and cooldowns). */
export const sendSmartAlertTest = ({ urgency = "wake_up", ruleId } = {}) =>
  ownerRequest("/api/smart-alerts/test", {
    method: "POST",
    body: ruleId ? { rule_id: Number(ruleId) } : { urgency },
  });

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
        priceAtAdd: Number.isFinite(Number(price)) ? Number(price) : null,
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
