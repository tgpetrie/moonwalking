// frontend/src/lib/api.js — cleaned, focused API helpers
const RAW_BASE = (import.meta.env?.VITE_API_URL || "").trim();
const API_BASE = RAW_BASE && RAW_BASE !== "relative" ? RAW_BASE.replace(/\/$/, "") : "";

const join = (path) => {
  if (!path) return path || "";
  if (/^(https?:)?\/\//i.test(path)) return path;
  if (!API_BASE) return path.startsWith("/") ? path : `/${path}`;
  return `${API_BASE.replace(/\/+$/, "")}/${String(path).replace(/^\/+/, "")}`;
};

export const endpoints = {
  metrics: "/data",
  sentiment: (s) => `/api/sentiment?symbol=${encodeURIComponent(s)}`,
};

export async function fetchJson(path, init = {}, ms = 9000) {
  const url = join(path);
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), ms);
  try {
    const res = await fetch(url, { credentials: "same-origin", ...init, signal: controller.signal });
    if (!res.ok) {
      const txt = await res.text().catch(() => "");
      throw new Error(`HTTP ${res.status} ${res.statusText} @ ${url}${txt ? ` :: ${txt.slice(0, 200)}` : ""}`);
    }
    return await res.json();
  } finally {
    clearTimeout(timer);
  }
}

export async function fetchSentiment(symbol) {
  if (!symbol) return null;
  return fetchJson(endpoints.sentiment(symbol));
}

export default { endpoints, fetchJson, fetchSentiment };
