// src/api.js
// Central API helpers and exports used across the frontend.
// `API_BASE_URL` may be set via Vite env (`VITE_API_URL`).
export const API_BASE_URL = import.meta.env.VITE_API_URL || '';
export const API_BASE = API_BASE_URL || '/api';

export const API_ENDPOINTS = {
  data: '/data',
  sentimentBasic: `${API_BASE}/sentiment-basic`,
  component: {
    gainers1m: `${API_BASE}/component/gainers-1m`,
    gainers3m: `${API_BASE}/component/gainers-table`,
    losers3m: `${API_BASE}/component/losers-table`,
  },
};

export async function fetchJson(path, opts = {}) {
  const res = await fetch(path, { headers: { Accept: 'application/json' }, ...opts });
  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(`HTTP ${res.status} ${res.statusText}: ${body}`);
  }
  return res.json();
}

export async function fetchData(path = '/api/data') {
  const base = API_BASE_URL || '';
  const url = path.startsWith('/') ? `${base}${path}` : `${base}/${path}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`fetch ${url} failed: ${res.status}`);
  return res.json();
}

// Convenience: fetch the main payload the app expects.
export async function fetchAllData() {
  // Prefer the proxied `/api/data` route; fall back to `/data` if needed.
  const base = API_BASE_URL || '';
  const tryUrls = [`${base}/api/data`, `${base}/data`, `/api/data`, `/data`];
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
