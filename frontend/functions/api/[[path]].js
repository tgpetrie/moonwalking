addEventListener('fetch', event => {
  event.respondWith(handleRequest(event.request))
})

async function handleRequest(request) {
  try {
    const url = new URL(request.url)
    // path after /api/
    const path = url.pathname.replace(/^\/api\//, '')

    // Determine backend origin from environment variables
    const env = GLOBAL_ENV || {};
    const backendOrigin = env.BACKEND_ORIGIN || env.PUBLIC_API_BASE_URL || env.API_BASE_URL || null;
    if (!backendOrigin) {
      return new Response(JSON.stringify({ error: 'No backend origin configured. Set BACKEND_ORIGIN or PUBLIC_API_BASE_URL.' }), {
        status: 500,
        headers: { 'Content-Type': 'application/json' }
      })
    }

    // Construct proxied URL
    const target = new URL(backendOrigin.replace(/\/$/, ''))
    target.pathname = `/api/${path}`
    target.search = url.search

    // Forward request method, headers, and body
    const init = {
      method: request.method,
      headers: request.headers,
      body: request.method === 'GET' || request.method === 'HEAD' ? null : await request.clone().arrayBuffer()
    }

    const resp = await fetch(target.toString(), init)

    // If backend returns 503 for banners, convert to empty payload for UX
    if (resp.status === 503 && /banner/i.test(path)) {
      const body = JSON.stringify({ items: [], updatedAt: Date.now() })
      return new Response(body, { status: 200, headers: { 'Content-Type': 'application/json' } })
    }

    // Pass through status and headers
    const headers = new Headers(resp.headers)
    return new Response(resp.body, { status: resp.status, headers })
  } catch (e) {
    return new Response(JSON.stringify({ error: String(e) }), { status: 500, headers: { 'Content-Type': 'application/json' } })
  }
}

// Helper to access environment in Cloudflare Pages Functions compatibility
const GLOBAL_ENV = typeof __STATIC_CONTENT_MANIFEST !== 'undefined' ? process.env : (typeof globalThis !== 'undefined' ? globalThis.__ENV__ : undefined)
// Request throttling to prevent resource exhaustion
export const config = { runtime: 'edge' };

const requestCache = new Map();
const CACHE_DURATION = 10000; // 10 seconds
const CACHE_DURATION_1MIN = 3000; // 3 seconds for fast 1-min panel

// Optional: only show custom-defined alerts (enable with VITE_ALERTS_CUSTOM_ONLY=1)
const ALERTS_CUSTOM_ONLY = (() => {
  const v = String(import.meta.env.VITE_ALERTS_CUSTOM_ONLY ?? "").toLowerCase();
  return v === "1" || v === "true" || v === "yes";
})();

// If enabled, filter /api/alerts/recent payloads down to "custom" alerts only
// Supports a few common shapes: array, {items:[]}, or {alerts:[]}
const maybeFilterCustomAlerts = (endpoint, data) => {
  try {
    if (!ALERTS_CUSTOM_ONLY) return data;
    if (!/\/api\/alerts\/recent(?:\b|\/|\?)/.test(endpoint)) return data;

    const pickArray = (obj) => {
      if (Array.isArray(obj)) return obj;
      if (obj && Array.isArray(obj.items)) return obj.items;
      if (obj && Array.isArray(obj.alerts)) return obj.alerts;
      return null;
    };

    const arr = pickArray(data);
    if (!arr) return data;

    const isCustom = (a) =>
      (a && (a.custom === true)) ||
      (a && a.kind === "custom") ||
      (a && a.source === "custom") ||
      (Array.isArray(a?.tags) && a.tags.includes("custom"));

    const filtered = arr.filter(isCustom);

    // Rebuild in the original shape
    if (Array.isArray(data)) return filtered;
    if (Array.isArray(data.items)) return { ...data, items: filtered };
    if (Array.isArray(data.alerts)) return { ...data, alerts: filtered };
    return data;
  } catch {
    return data;
  }
};

async function fetchData(endpoint) {
  const now = Date.now();

  // Check cache first with per-endpoint TTL
  if (requestCache.has(endpoint)) {
    const cached = requestCache.get(endpoint);
    // Use shorter TTL for 1-minute table requests
    const ttl = endpoint.includes('gainers-table-1min') ? CACHE_DURATION_1MIN : CACHE_DURATION;
    if (now - cached.timestamp < ttl) {
      return cached.data;
    }
  }

  // Fetch from API base URL
  const apiBase = getApiBaseUrl();
  const fullUrl = apiBase + endpoint;

  try {
    const response = await fetch(fullUrl);

    if (response.ok) {
      const raw = await response.json();
      const data = maybeFilterCustomAlerts(endpoint, raw);
      requestCache.set(endpoint, { data, timestamp: now });
      return data;
    }

    // If API base fails, try fallback
    const fallbackBase = getFallbackApiBaseUrl();
    if (fallbackBase && fallbackBase !== apiBase) {
      const newEndpoint = fallbackBase + endpoint;
      const retryRes = await fetch(newEndpoint);

      if (retryRes.ok) {
        // Commit base change only after endpoint success
        setApiBaseUrl(fallbackBase);
        const raw = await retryRes.json();
        const data = maybeFilterCustomAlerts(newEndpoint, raw);
        requestCache.set(newEndpoint, { data, timestamp: Date.now() });
        return data;
      }
    }
  } catch (error) {
    console.error("Fetch error:", error);
  }

  throw new Error("Failed to fetch data");
}

// Default handler: proxy request, apply edge-cache headers, and return JSON response
export default async function handler(request, context) {
  const { params } = context;
  // Build endpoint from catch-all `path` parameter
  const segments = Array.isArray(params.path)
    ? params.path
    : params.path
    ? [params.path]
    : [];
  const endpoint = segments.length ? '/' + segments.join('/') : '/';

  try {
    const data = await fetchData(endpoint);
    const body = JSON.stringify(data);
    const headers = new Headers({
      'Content-Type': 'application/json',
      'Cache-Control': 'public, max-age=10, stale-while-revalidate=59'
    });
    return new Response(body, { headers });
  } catch (err) {
    console.error('Proxy handler error:', err);
    return new Response(JSON.stringify({ error: err.message }), { status: 500 });
  }
}
