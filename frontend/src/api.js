// src/api.js
// always fetch relative to the Vite dev server, let Vite proxy to 5001

export const API_BASE = '/api';

export const API_ENDPOINTS = {
  data: '/data',
  sentimentBasic: `${API_BASE}/sentiment-basic`,
  component: {
    gainers1m: `${API_BASE}/component/gainers-1m`,
    gainers3m: `${API_BASE}/component/gainers-table`,
    losers3m:  `${API_BASE}/component/losers-table`,
  },
};

// simple GET helper used by components
export async function getJson(path, opts = {}) {
  const res = await fetch(path, { headers: { Accept: 'application/json' }, ...opts });
  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(`HTTP ${res.status} ${res.statusText}: ${body}`);
  }
  return res.json();
}

export async function fetchData(path = "/data") {
  const res = await fetch(path);
  if (!res.ok) {
    throw new Error(`fetch ${path} failed: ${res.status}`);
  }
  return res.json();
}

