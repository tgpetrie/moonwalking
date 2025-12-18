// src/api.js
// Central API helpers and exports used across the frontend.
// `VITE_API_URL` should be the backend ORIGIN (no trailing `/api`).
// We defensively normalize it anyway so we never generate `/api/api/*`.

// Force relative path by default to use Vite proxy
const rawBase = String(import.meta.env.VITE_API_BASE_URL || '').trim();
const baseNoTrailingSlash = rawBase.replace(/\/+$/, '');
// If someone sets VITE_API_URL=http://host:port/api, strip the trailing /api
const normalizedBase = baseNoTrailingSlash.replace(/\/+api$/, '');

export const API_BASE_URL = normalizedBase;
export const API_ORIGIN = normalizedBase;
// Base for API routes (relative in dev when no origin is set)
export const API_BASE = API_ORIGIN ? `${API_ORIGIN}/api` : '/api';

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
  data: joinUrl(API_ORIGIN, '/data'),
  sentimentBasic: joinUrl(API_ORIGIN, '/api/sentiment-basic'),
  component: {
    gainers1m: joinUrl(API_ORIGIN, '/api/component/gainers-1m'),
    gainers3m: joinUrl(API_ORIGIN, '/api/component/gainers-table'),
    losers3m: joinUrl(API_ORIGIN, '/api/component/losers-table'),
  },
};

export async function fetchJson(path, opts = {}) {
  const url = joinUrl(API_ORIGIN, path);
  const res = await fetch(url, { headers: { Accept: 'application/json' }, ...opts });
  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(`HTTP ${res.status} ${res.statusText}: ${body}`);
  }
  return res.json();
}

export async function fetchData(path = '/data') {
  const url = joinUrl(API_ORIGIN, path);
  const res = await fetch(url);
  if (!res.ok) throw new Error(`fetch ${url} failed: ${res.status}`);
  return res.json();
}

// Convenience: fetch the main payload the app expects.
export async function fetchAllData() {
  // Prefer canonical `/data`; keep `/api/data` as a backwards-compatible alias.
  const tryUrls = [
    joinUrl(API_ORIGIN, '/data'),
    joinUrl(API_ORIGIN, '/api/data'),
    '/data',
    '/api/data',
  ];
  let lastErr = null;
  for (const url of tryUrls) {
    try {
      const res = await fetch(url);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    } catch (err) {
      lastErr = err;
    }
  }
  throw lastErr || new Error('fetchAllData: no available endpoint');
}

export const fetchAllDataApi = fetchAllData;

export default { API_BASE_URL, API_BASE, API_ENDPOINTS, fetchJson, fetchData, fetchAllData };
