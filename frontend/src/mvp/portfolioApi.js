import { getBackendBase } from "../config/api.js";

function apiUrl(pathname) {
  const path = pathname.startsWith("/") ? pathname : `/${pathname}`;
  return `${getBackendBase()}${path}`;
}

export class PortfolioApiError extends Error {
  constructor(message, response, payload) {
    super(message);
    this.name = "PortfolioApiError";
    this.status = response?.status || 0;
    this.payload = payload || {};
  }
}

async function jsonRequest(pathname) {
  const response = await fetch(apiUrl(pathname), {
    credentials: "include",
    headers: { Accept: "application/json" },
  });
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : {};
  if (!response.ok) {
    throw new PortfolioApiError(
      payload?.error || `Request failed with status ${response.status}`,
      response,
      payload
    );
  }
  return payload;
}

export function fetchPortfolio({ force = false } = {}) {
  return jsonRequest(`/api/portfolio${force ? "?refresh=1" : ""}`);
}

// Progressive enhancement: prefer the signal-enriched snapshot, but fall back
// to the plain one when intel is unavailable to this user (currently owner-only,
// returns 403 for OAuth users). The base snapshot has the same shape minus the
// `.intel` fields, so callers render intel only when present.
export async function fetchPortfolioIntel({ force = false } = {}) {
  try {
    const enriched = await jsonRequest(`/api/portfolio/intel${force ? "?refresh=1" : ""}`);
    return { ...enriched, intel_available: true };
  } catch (error) {
    if (error instanceof PortfolioApiError && (error.status === 403 || error.status === 503)) {
      const base = await fetchPortfolio({ force });
      return { ...base, intel_available: false };
    }
    throw error;
  }
}

export function fetchPortfolioMarketContext() {
  return jsonRequest("/data");
}

export function fetchCoinbaseOAuthStatus() {
  return jsonRequest("/api/oauth/coinbase/status");
}

// The authorize route responds with a 302 to Coinbase's consent screen, so the
// browser must navigate to it directly — this is not an XHR-able endpoint.
export function coinbaseAuthorizeUrl() {
  return apiUrl("/api/oauth/coinbase/authorize");
}

export async function disconnectCoinbaseOAuth() {
  const response = await fetch(apiUrl("/api/oauth/coinbase/disconnect"), {
    method: "POST",
    credentials: "include",
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new PortfolioApiError("Failed to disconnect Coinbase OAuth.", response, {});
  }
  return response.json().catch(() => ({ success: true }));
}
