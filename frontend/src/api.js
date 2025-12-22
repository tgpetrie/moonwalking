// src/api.js
// Central API helpers and exports used across the frontend.
// Prefer relative path by default to let Vite proxy handle dev routing.
const API_BASE = (import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_URL || "").replace(/\/+$/, "");
export const API_BASE_URL = API_BASE;
export const API_ORIGIN = API_BASE;

function isAbsoluteUrl(s) {
  return /^https?:\/\//i.test(s);
}

function joinUrl(base, path) {
  const p = String(path || '');
  if (!p) return base || '';
  if (isAbsoluteUrl(p)) return p;
  const baseClean = String(base || '').replace(/\/+$/, '');
  const pathClean = p.startsWith('/') ? p : `/${p}`;
  return baseClean ? `${baseClean}${pathClean}` : pathClean;
}

export const API_ENDPOINTS = {
  // Canonical snapshot endpoint is /data
  data: joinUrl(API_BASE, '/api/data'),
  sentimentBasic: joinUrl(API_BASE, '/api/sentiment-basic'),
  component: {
    gainers1m: joinUrl(API_BASE, '/api/component/gainers-1m'),
    gainers3m: joinUrl(API_BASE, '/api/component/gainers-table'),
    losers3m: joinUrl(API_BASE, '/api/component/losers-table'),
  },
};

// Ensure the frontend always receives the canonical payload structure
function normalizeApi(payload) {
  const p = payload && typeof payload === 'object' && payload.data && typeof payload.data === 'object' ? payload.data : payload || {};

  return {
    // keep original keys but ensure canonical fallbacks
    ...p,
    banner_1h_price: Array.isArray(p.banner_1h_price) ? p.banner_1h_price : (p.banner_1h_price ? p.banner_1h_price : []),
    banner_1h_volume: Array.isArray(p.banner_1h_volume) ? p.banner_1h_volume : (p.banner_1h_volume ? p.banner_1h_volume : []),
    gainers_1m: Array.isArray(p.gainers_1m) ? p.gainers_1m : [],
    gainers_3m: Array.isArray(p.gainers_3m) ? p.gainers_3m : [],
    losers_3m: Array.isArray(p.losers_3m) ? p.losers_3m : [],

    latest_by_symbol: p.latest_by_symbol ?? {},
    meta: p.meta ?? {},
    updated_at: p.updated_at ?? null,
    errors: (p.errors && typeof p.errors === "object") ? p.errors : {},
    coverage: p.coverage ?? null,
  };
}

export async function fetchJson(path, opts = {}) {
  const url = joinUrl(API_ORIGIN, path);
  const res = await fetch(url, { headers: { Accept: 'application/json' }, ...opts });
  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(`HTTP ${res.status} ${res.statusText}: ${body}`);
  }
  return res.json();
}

export async function fetchData(path = '/api/data') {
  const url = joinUrl(API_BASE, path);
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`fetch ${url} failed: ${res.status}`);
  const json = await res.json();
  return normalizeApi(json);
}

// Convenience: fetch the main payload the app expects.
export async function fetchAllData(keyUrl) {
  if (typeof keyUrl === "string" && keyUrl.trim()) {
    const u = keyUrl.trim();

    // Same-origin path like "/api/data" should be fetched exactly.
    if (u.startsWith("/")) {
      const res = await fetch(u, { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      return normalizeApi(json);
    }

    // Absolute URL: try as-is only
    const res = await fetch(u, { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const json = await res.json();
    return normalizeApi(json);
  }

  const base = API_BASE || "";
  const tryUrls = [`${base}/api/data`, `${base}/data`];
  let lastErr = null;

  for (const url of tryUrls) {
    try {
      const res = await fetch(url, { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      return normalizeApi(json);
    } catch (err) {
      lastErr = err;
    }
  }
  throw lastErr || new Error("fetchAllData: no available endpoint");
}

export const fetchAllDataApi = fetchAllData;

export default { API_BASE_URL, API_BASE, API_ENDPOINTS, fetchJson, fetchData, fetchAllData };
