// Lightweight API helpers used by the frontend.
export const API_BASE =
  import.meta.env.VITE_BACKEND_URL?.replace(/\/+$/, '') ||
  `${window.location.protocol}//${window.location.hostname}:5001`;

export const API_ENDPOINTS = {
  alertsRecent: `${API_BASE}/api/alerts/recent?limit=25`,
  topBanner: `${API_BASE}/api/component/top-banner-scroll`,
  bottomBanner: `${API_BASE}/api/component/bottom-banner-scroll`,
  t1m: `${API_BASE}/api/component/gainers-table-1min`,
  t3m: `${API_BASE}/api/component/gainers-table`,
};

export async function getJSON(url, opts = {}) {
  const res = await fetch(url, {
    headers: { Accept: 'application/json' },
    ...opts,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(
      `HTTP ${res.status} ${url}${text ? ` — ${text.slice(0, 120)}` : ''}`,
    );
  }
  return res.json();
}

// simple in-memory de-dupe for concurrent calls
const inflight = new Map();

export async function fetchWithSWR(url) {
  const key = `cache:${url}`;
  const cached = sessionStorage.getItem(key);
  if (cached) {
    // revalidate in background, but don't block paint
    getJSON(url)
      .then((data) => sessionStorage.setItem(key, JSON.stringify(data)))
      .catch(() => {});
    try {
      const parsed = JSON.parse(cached);
      return parsed.data || parsed;
    } catch (e) {
      // fallthrough to live fetch
    }
  }

  // de-dupe concurrent fetches
  if (!inflight.has(url)) {
    inflight.set(
      url,
      getJSON(url).finally(() => {
        inflight.delete(url);
      }),
    );
  }
  const data = await inflight.get(url);
  sessionStorage.setItem(key, JSON.stringify(data));
  return data;
}

// Lightweight React hook for components. Named export for tests and direct imports.
import React, { useEffect, useState } from 'react'

export function useEndpoint(endpoint, { pollMs = 0, normalizer = null } = {}) {
  const key = `cache:${endpoint}`
  const initial = (() => {
    try {
      const snap = sessionStorage.getItem(key)
      if (!snap) return null
      const parsed = JSON.parse(snap)
      return parsed?.data ?? parsed
    } catch (e) {
      return null
    }
  })()

  const [data, setData] = useState(initial)
  // if we have an initial cached snapshot, tests expect loading to be false
  const [loading, setLoading] = useState(initial == null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let alive = true

    async function doFetch() {
      setLoading(true)
      setError(null)
      try {
        const raw = await fetchWithSWR(endpoint)
        if (!alive) return
        const out = typeof normalizer === 'function' ? normalizer(raw) : raw
        setData(out)
        setLoading(false)
      } catch (e) {
        if (!alive) return
        setError(e)
        setLoading(false)
      }
    }

    doFetch()

    let id
    if (pollMs > 0) {
      id = setInterval(() => { doFetch() }, pollMs)
    }

    return () => { alive = false; if (id) clearInterval(id) }
  }, [endpoint, pollMs])

  // historic consumers (tests) expect tuple [data, loading, error]
  return [data, loading, error]
}

// Provide getApiBaseUrl and a tiny in-page bus and share helpers for other modules/tests that expect them
export function getApiBaseUrl() {
  return API_BASE
}

const _eventListeners = new Map()
const _globalListeners = new Set()

export const bus = {
  // bus.on(fn) -> global listener (receives { type, payload })
  // bus.on(evt, fn) -> event-specific listener (receives payload)
  on(a, b) {
    if (typeof a === 'function' && b === undefined) {
      _globalListeners.add(a)
      return () => { _globalListeners.delete(a) }
    }
    const evt = a
    const fn = b
    const arr = _eventListeners.get(evt) || []
    arr.push(fn)
    _eventListeners.set(evt, arr)
    return () => {
      const a2 = _eventListeners.get(evt) || []
      _eventListeners.set(evt, a2.filter(f => f !== fn))
    }
  },
  emit(evt, payload) {
    // call event-specific listeners with payload
    const arr = _eventListeners.get(evt) || []
    for (const fn of arr) {
      try { fn(payload) } catch (e) { try { console.error('[bus]', evt, e) } catch (_) {} }
    }
    // call global listeners with envelope
    const envelope = { type: evt, payload }
    for (const g of Array.from(_globalListeners)) {
      try { g(envelope) } catch (e) { try { console.error('[bus] global', e) } catch (_) {} }
    }
  }
}

export function shareTables(payload) {
  try { sessionStorage.setItem('tables:last', JSON.stringify(payload || {})) } catch (_){ }
}

export function shareAlerts(payload) {
  try { sessionStorage.setItem('alerts:last', JSON.stringify(payload || { items: [] })) } catch (_){ }
}

export async function fetchJSON(url, options = {}) {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });

  const text = await res.text();
  let data;
  try {
    data = text ? JSON.parse(text) : null;
  } catch (err) {
    // non-JSON response
    const e = new Error("Invalid JSON response");
    e.responseText = text;
    e.originalError = err;
    throw e;
  }

  if (!res.ok) {
    const e = new Error(data?.message || `HTTP ${res.status}`);
    e.status = res.status;
    e.data = data;
    throw e;
  }

  return data;
}