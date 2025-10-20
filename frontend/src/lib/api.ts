// frontend/src/lib/api.ts
// Minimal, safe API utilities (HTTP helpers only).

export const API_BASE: string = (import.meta as any)?.env?.VITE_API_BASE || "";

export async function httpGet<T = any>(path: string, init: RequestInit = {}): Promise<T> {
  const url = path.startsWith("http") ? path : `${API_BASE}${path}`;
  const res = await fetch(url, {
    credentials: "same-origin",
    ...init,
    method: "GET",
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    const suffix = text ? `: ${text}` : "";
    throw new Error(`HTTP ${res.status}${suffix}`);
  }
  return (await res.json()) as T;
}

// Back-compat alias used across hooks/components
export const fetchComponent = httpGet;

// Convenience helpers for common endpoints
export const getGainers1m = () => httpGet("/api/component/gainers-table-1min");
export const getGainers3m = () => httpGet("/api/component/gainers-table");
export const getLosers3m = () => httpGet("/api/component/losers-table");
export const getPriceBanner1h = () => httpGet("/api/banner/one-hour-price");
export const getVolumeBanner1h = () => httpGet("/api/banner/one-hour-volume");

// Backwards-compatible convenience object used by some pages (e.g. Status.tsx)
export const api = {
  health: () => httpGet('/api/health'),
  metrics: () => httpGet('/api/metrics'),
};