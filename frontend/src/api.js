// frontend/src/api.js — single, boring HTTP helper that stays on /data
const BASE = (import.meta.env?.VITE_API_BASE || "").replace(/\/+$/, "");
const API_BASE = "/api";
const normalizePath = (path) => {
  if (!path) return "";
  return path.startsWith("/") ? path : `/${path}`;
};
const withBase = (path) => `${BASE}${normalizePath(path)}`;

export const API_ENDPOINTS = {
  data: "/data",
  apiData: "/api/data",
  metrics: "/data", // alias used by some hooks
  sentimentBasic: `${API_BASE}/sentiment-basic`,
  sentiment: (symbol) => `${API_BASE}/sentiment?symbol=${encodeURIComponent(symbol || "")}`,
  gainersTable1Min: `${API_BASE}/component/gainers-table-1min`,
  gainersTable3Min: `${API_BASE}/component/gainers-table-3min`,
  losersTable3Min: `${API_BASE}/component/losers-table-3min`,
  gainers: `${API_BASE}/component/gainers-table`,
  bottomBanner: `${API_BASE}/component/bottom-banner-scroll`,
  topBanner: `${API_BASE}/component/top-banner-scroll`,
  banner1h: `${API_BASE}/component/top-banner-scroll`,
  topMoversBar: `${API_BASE}/component/top-movers-bar`,
  alertsRecent: `${API_BASE}/alerts/recent`,
  watchlistInsights: `${API_BASE}/component/watchlist-insights`,
  serverInfo: `${API_BASE}/server-info`,
  technicalAnalysis: (symbol) => `${API_BASE}/technical-analysis/${encodeURIComponent(symbol || "")}`,
  cryptoNews: (symbol) => `${API_BASE}/news/${encodeURIComponent(symbol || "")}`,
  socialSentiment: (symbol) => `${API_BASE}/social-sentiment/${encodeURIComponent(symbol || "")}`,
};

// Single fetch helper used everywhere
export async function fetchJson(path, init = {}) {
  const url = withBase(path);
  const headers = { Accept: "application/json", ...(init.headers || {}) };
  const res = await fetch(url, { ...init, headers });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`Fetch failed for ${path}: ${res.status} ${res.statusText}${body ? ` :: ${body.slice(0, 200)}` : ""}`);
  }
  return res.json();
}

export async function fetchAllData() {
  return fetchJson("/data");
}

// Legacy alias; keep for compatibility if referenced
export async function fetchAllDataApi() {
  return fetchJson("/api/data");
}

// Generic helper kept for components that still call fetchData(path)
export async function fetchData(path = "/data", opts = {}) {
  return fetchJson(path, opts);
}

// ---- Watchlist helpers (localStorage-backed) ---------------------------
const WATCHLIST_KEY = "watchlist";

export function getWatchlist() {
  try {
    const raw = localStorage.getItem(WATCHLIST_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch (err) {
    return [];
  }
}

export function setWatchlist(nextList) {
  try {
    const arr = Array.isArray(nextList) ? nextList : [];
    localStorage.setItem(WATCHLIST_KEY, JSON.stringify(arr));
    return arr;
  } catch (err) {
    return [];
  }
}

export function addToWatchlist(symbol) {
  const s = (symbol || "").toUpperCase().trim();
  if (!s) return getWatchlist();
  const list = getWatchlist();
  if (!list.includes(s)) list.push(s);
  return setWatchlist(list);
}

export function removeFromWatchlist(symbol) {
  const s = (symbol || "").toUpperCase().trim();
  const list = getWatchlist().filter((x) => x !== s);
  return setWatchlist(list);
}
