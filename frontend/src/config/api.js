/**
 * Single source of truth for API base URLs and configuration.
 * All backend/brains URL logic should import from here.
 */

// ============================================================================
// BLOCKED PORTS (legacy/deprecated)
// ============================================================================
const BLOCKED_PORTS = [8001, 8003];
const BLOCKED_PORT_RE = new RegExp(`:(?:${BLOCKED_PORTS.join('|')})$`, 'i');

// ============================================================================
// BACKEND CONFIG (Flask data + alerts service)
// ============================================================================

/**
 * Canonical backend base for dev: empty string (uses Vite proxy)
 * In dev, requests to /data, /api/... are proxied to 127.0.0.1:5003
 */
export const BACKEND_BASE_DEV = "";

/**
 * Get backend base URL from environment or use dev default
 */
export function getBackendBase() {
  const envBase = (
    import.meta.env.VITE_API_BASE ||
    import.meta.env.VITE_API_BASE_URL ||
    import.meta.env.VITE_API_URL ||
    ""
  ).trim().replace(/\/+$/, "");

  // If env specifies a full URL, use it; otherwise use dev default
  if (envBase.startsWith("http")) {
    return sanitizeBase(envBase);
  }
  return BACKEND_BASE_DEV;
}

/**
 * Get backend candidates.
 * Contract:
 * - Prefer explicit env base first when present.
 * - Always include same-origin (Vite proxy) and local direct fallbacks.
 * This prevents a single bad proxy/base from freezing the UI.
 */
export function getBackendCandidates() {
  const out = [];
  const envBase = getBackendBase();
  if (envBase && envBase !== BACKEND_BASE_DEV) {
    pushCandidate(out, envBase);
  }
  pushCandidate(out, BACKEND_BASE_DEV);
  pushCandidate(out, "http://127.0.0.1:5003");
  pushCandidate(out, "http://localhost:5003");
  return out.length ? out : [BACKEND_BASE_DEV];
}

// ============================================================================
// BRAINS CONFIG (insights/intelligence service - STRICT PORTS ONLY)
// ============================================================================

/**
 * STRICT brains port: 8002 only
 * If brains isn't reachable here, it's offline - no port hunting
 */
export const BRAINS_STRICT_BASES = [
  "http://127.0.0.1:8002",
  "http://localhost:8002",
];

/**
 * Get brains base URLs (STRICT - no discovery, no fallback to random ports)
 */
export function getBrainsCandidates() {
  return [...BRAINS_STRICT_BASES];
}

// ============================================================================
// VALIDATION & NORMALIZATION
// ============================================================================

/**
 * Normalize a base URL: trim, remove trailing slashes
 */
export function normalizeBase(url) {
  return String(url || "").trim().replace(/\/+$/, "");
}

/**
 * Check if a URL contains a blocked port
 */
export function isBlockedPort(url) {
  const normalized = normalizeBase(url);
  return BLOCKED_PORT_RE.test(normalized);
}

/**
 * Sanitize a base URL: normalize and block legacy ports
 */
export function sanitizeBase(url) {
  const normalized = normalizeBase(url);
  return isBlockedPort(normalized) ? "" : normalized;
}

/**
 * Push a candidate base to a list (dedupe, skip blocked ports)
 */
function pushCandidate(list, base) {
  const normalized = normalizeBase(base);

  // Skip blocked ports
  if (isBlockedPort(normalized)) {
    return;
  }

  // Skip duplicates
  if (list.some(x => normalizeBase(x) === normalized)) {
    return;
  }

  list.push(normalized);
}

// ============================================================================
// LOCALSTORAGE KEYS
// ============================================================================

export const LS_BACKEND_KEY = "mw_backend_base";

/**
 * Clean up stale/blocked localStorage entries
 * Call this on app startup to purge any cached :8001 references
 */
export function cleanupStaleCache() {
  if (typeof window === "undefined") return;

  try {
    const cached = window.localStorage.getItem(LS_BACKEND_KEY);
    if (!cached) return;

    const normalized = normalizeBase(cached);
    if (isBlockedPort(normalized)) {
      console.info("[config] Removing blocked cached base:", normalized);
      window.localStorage.removeItem(LS_BACKEND_KEY);
    }
  } catch (err) {
    console.warn("[config] Failed to cleanup stale cache:", err);
  }
}

// ============================================================================
// JSON-SAFE FETCH WRAPPER
// ============================================================================

/**
 * Fetch with JSON safety: checks content-type before parsing
 * Prevents "Unexpected identifier 'OK'/'NO'" crashes
 *
 * @param {string} url - URL to fetch
 * @param {RequestInit} options - Fetch options
 * @returns {Promise<{ok: boolean, status: number, json: any|null, error: string|null}>}
 */
export async function safeFetch(url, options = {}) {
  try {
    const response = await fetch(url, options);

    // Check if response is OK
    if (!response.ok) {
      return {
        ok: false,
        status: response.status,
        json: null,
        error: `HTTP ${response.status}`,
      };
    }

    // Check content-type
    const contentType = response.headers.get("content-type") || "";
    const isJson = contentType.includes("application/json");

    if (!isJson) {
      const text = await response.text();
      console.warn("[safeFetch] Non-JSON response:", { url, contentType, preview: text.slice(0, 100) });
      return {
        ok: false,
        status: response.status,
        json: null,
        error: `Expected JSON, got ${contentType}`,
      };
    }

    // Safe to parse JSON
    const json = await response.json();
    return {
      ok: true,
      status: response.status,
      json,
      error: null,
    };
  } catch (err) {
    // Network error, abort, etc.
    return {
      ok: false,
      status: 0,
      json: null,
      error: err.message || String(err),
    };
  }
}
