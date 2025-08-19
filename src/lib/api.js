// frontend/src/lib/api
// Shared API + WebSocket helpers for HTTP+WS through Cloudflare Pages (/api, /ws)
// - In production (non-localhost): HTTP -> same-origin /api, WS -> same-origin /ws/socket.io
// - In dev (localhost): HTTP -> http://localhost:5001, WS -> http://localhost:5001/socket.io

const DEFAULT_DEV_HTTP = "http://localhost:5001";

let _apiBase = null;

// Resolve the HTTP API base (used by fetch calls)
export function getApiBaseUrl() {
  if (_apiBase) return _apiBase;

  const isLocal =
    location.hostname === "localhost" ||
    location.hostname === "127.0.0.1";

  // Allow override via Vite env
  const envBase = import.meta?.env?.VITE_API_BASE;

  if (isLocal) {
    _apiBase = envBase || DEFAULT_DEV_HTTP;
  } else {
    // In production, same-origin Pages function `/api` should exist (proxying to backend)
    _apiBase = `${location.origin}/api`;
  }
  return _apiBase;
}

export function setApiBaseUrl(url) {
  _apiBase = url;
}

// Build full URL for a relative API path
export function apiUrl(path) {
  // If caller passes absolute URL, leave as-is
  if (/^https?:\/\//i.test(path)) return path;
  const base = getApiBaseUrl();
  // Ensure single slash
  return `${base.replace(/\/+$/, "")}/${path.replace(/^\/+/, "")}`;
}

/**
 * WebSocket (Socket.IO) endpoint configuration
 * Returns { url, path } for the Socket.IO client.
 *
 * In production, we connect to same-origin and use a Cloudflare Pages Function at `/ws`
 * that proxies to the backend `/socket.io`. Socket.IO wants its engine path, so we use:
 *   url: location.origin
 *   path: '/ws/socket.io'
 *
 * In development, connect directly to the backend on :5001 with the default '/socket.io' path.
 */
export function getWsConfig() {
  const isLocal =
    location.hostname === "localhost" ||
    location.hostname === "127.0.0.1";

  const devTarget = (import.meta?.env?.VITE_API_BASE || DEFAULT_DEV_HTTP);

  if (isLocal) {
    return {
      url: devTarget,          // e.g. http://localhost:5001
      path: "/socket.io",      // backend default
    };
  }
  return {
    url: location.origin,      // same-origin (Cloudflare Pages)
    path: "/ws/socket.io",     // Pages Function proxy
  };
}

/**
 * Lightweight request cache + de-dupe with per-route TTLs.
 */
const requestCache = new Map();
const inflight = new Map();
const TTL = {
  "/api/alerts/recent": 5000,
  "/api/component/gainers-table-1min": 2500,
  "/api/component/gainers-table": 10000,
  "/api/component/losers-table": 10000,
  "/api/component/top-banner-scroll": 15000,
  "/api/component/bottom-banner-scroll": 15000,
  default: 8000,
};

function ttlFor(url) {
  for (const k of Object.keys(TTL)) if (k !== "default" && url.includes(k)) return TTL[k];
  return TTL.default;
}

export function maybeFilterCustomAlerts(endpoint, payload) {
  // placeholder for any endpoint-specific shaping
  return payload;
}

export async function fetchData(endpoint, opts = {}) {
  const url = apiUrl(endpoint);
  const now = Date.now();
  const cacheTtl = ttlFor(url);
  const cached = requestCache.get(url);
  if (cached && (now - cached.timestamp) < cacheTtl) return cached.data;

  if (inflight.has(url)) return inflight.get(url);

  const controller = new AbortController();
  const p = (async () => {
    try {
      const res = await fetch(url, { ...opts, signal: controller.signal, credentials: "include" });
      if (!res.ok) throw new Error(`HTTP ${res.status} for ${url}`);
      const raw = await res.json();
      const data = maybeFilterCustomAlerts(url, raw);
      requestCache.set(url, { data, timestamp: Date.now() });
      return data;
    } finally {
      inflight.delete(url);
    }
  })();

  inflight.set(url, p);
  return p;
}

// Stale-While-Revalidate helper
export async function fetchWithSWR(endpoint, opts = {}) {
  const key = `cache:${endpoint}`;
  const cached = sessionStorage.getItem(key);
  if (cached) {
    // fire-and-forget revalidation
    fetchData(endpoint, opts).catch(() => {});
    return JSON.parse(cached);
  }
  const data = await fetchData(endpoint, opts);
  sessionStorage.setItem(key, JSON.stringify(data));
  return data;
}

// Tiny in-page event bus (for multi-component fanout without re-render storms)
const _listeners = new Map();
export const bus = {
  on(evt, fn) {
    const arr = _listeners.get(evt) || [];
    arr.push(fn);
    _listeners.set(evt, arr);
    return () => {
      const a = _listeners.get(evt) || [];
      _listeners.set(evt, a.filter(f => f !== fn));
    };
  },
  emit(evt, payload) {
    const arr = _listeners.get(evt) || [];
    for (const fn of arr) {
      try { fn(payload); } catch (e) { console.error("[bus]", evt, e); }
    }
  },
};