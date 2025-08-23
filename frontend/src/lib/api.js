// Lightweight API helpers used by the frontend.
export const API_BASE =
  import.meta.env.VITE_BACKEND_URL?.replace(/\/+$/, '') ||
  `${window.location.protocol}//${window.location.hostname}:5002`;

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

// Enhanced in-memory de-dupe with AbortController support
const inflight = new Map();
const controllers = new Map();

// Per-route TTL configuration (milliseconds)
const routeTTLs = {
  'gainers-table-1min': 10000,     // 10s for 1-min data
  'gainers-table': 30000,          // 30s for 3-min data
  'losers-table': 30000,           // 30s
  'alerts/recent': 5000,           // 5s for alerts
  'top-banner-scroll': 60000,      // 1min
  'bottom-banner-scroll': 60000,   // 1min
  default: 30000                   // 30s default
};

// Get TTL for a specific URL
function getTTLForUrl(url) {
  for (const [route, ttl] of Object.entries(routeTTLs)) {
    if (url.includes(route)) return ttl;
  }
  return routeTTLs.default;
}

export async function fetchWithSWR(url, options = {}) {
  const key = `cache:${url}`;
  const cached = sessionStorage.getItem(key);
  const ttl = getTTLForUrl(url);
  
  if (cached && !options.force) {
    try {
      const parsed = JSON.parse(cached);
      const age = Date.now() - (parsed.timestamp || 0);
      
      if (age < ttl) {
        // Data is still fresh, return immediately
        console.log(`💾 SWR cache hit: ${url} (age: ${age}ms, TTL: ${ttl}ms)`);
        return parsed.data || parsed;
      } else {
        // Data is stale, return stale data but revalidate in background
        console.log(`🔄 SWR stale-while-revalidate: ${url} (age: ${age}ms)`);
        backgroundRevalidate(url);
        return parsed.data || parsed;
      }
    } catch (e) {
      console.warn('SWR cache parse error:', e);
      // fallthrough to live fetch
    }
  }

  return performFetch(url, options);
}

// Background revalidation for SWR
async function backgroundRevalidate(url) {
  try {
    const data = await performFetch(url, { background: true });
    const key = `cache:${url}`;
    sessionStorage.setItem(key, JSON.stringify({
      data,
      timestamp: Date.now()
    }));
    console.log(`✅ Background revalidation complete: ${url}`);
  } catch (error) {
    console.warn(`⚠️ Background revalidation failed: ${url}`, error);
  }
}

// Core fetch with deduplication and AbortController
async function performFetch(url, options = {}) {
  // Abort previous request if exists
  if (controllers.has(url)) {
    console.log(`🔄 Aborting previous request: ${url}`);
    controllers.get(url).abort();
  }

  // Create new AbortController
  const controller = new AbortController();
  controllers.set(url, controller);

  // de-dupe concurrent fetches
  if (!inflight.has(url)) {
    const fetchPromise = getJSON(url, { 
      signal: controller.signal,
      ...options 
    }).then(data => {
      // Cache successful response with timestamp
      if (!options.background) {
        const key = `cache:${url}`;
        sessionStorage.setItem(key, JSON.stringify({
          data,
          timestamp: Date.now()
        }));
      }
      return data;
    }).finally(() => {
      inflight.delete(url);
      controllers.delete(url);
    });
    
    inflight.set(url, fetchPromise);
  }
  
  return inflight.get(url);
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

// Utility functions for cache and request management
export function clearAPICache(urlPattern = null) {
  if (urlPattern) {
    // Clear specific cache entries
    Object.keys(sessionStorage).forEach(key => {
      if (key.startsWith('cache:') && key.includes(urlPattern)) {
        sessionStorage.removeItem(key);
        console.log(`🗑️ Cleared cache: ${key}`);
      }
    });
  } else {
    // Clear all API cache
    Object.keys(sessionStorage).forEach(key => {
      if (key.startsWith('cache:')) {
        sessionStorage.removeItem(key);
      }
    });
    console.log('🗑️ Cleared all API cache');
  }
}

export function abortAllRequests() {
  let aborted = 0;
  for (const [url, controller] of controllers.entries()) {
    try {
      controller.abort();
      aborted++;
    } catch (e) {
      console.warn(`Failed to abort request: ${url}`, e);
    }
  }
  controllers.clear();
  inflight.clear();
  console.log(`🛑 Aborted ${aborted} requests`);
}

export function getAPIStats() {
  const cacheKeys = Object.keys(sessionStorage).filter(k => k.startsWith('cache:'));
  return {
    cacheEntries: cacheKeys.length,
    inFlightRequests: inflight.size,
    activeControllers: controllers.size,
    cacheSize: cacheKeys.reduce((size, key) => {
      try {
        return size + sessionStorage.getItem(key).length;
      } catch {
        return size;
      }
    }, 0)
  };
}