// frontend/src/lib/api.ts
// Centralised endpoint map + fetch helpers + response mappers.

const rawBase = String(((import.meta as any)?.env?.VITE_API_URL ?? "") || "");
const trimmedBase = rawBase.trim();
export const API_BASE =
  trimmedBase && trimmedBase !== "relative" ? trimmedBase.replace(/\/$/, "") : "";

if (typeof window !== "undefined") {
  (window as any).__API_BASE__ = API_BASE;
}

const preferredBase = API_BASE || "";
const normalise = (path: string) => {
  if (!path) return path;
  if (path.startsWith("http")) return path;
  if (path.startsWith("/")) return `${preferredBase}${path}`;
  return `${preferredBase}/${path}`;
};

export const endpoints = {
  banner1h: normalise("/api/component/top-movers-bar"),
  bannerVolume1h: normalise("/api/component/banner-volume-1h"),
  gainers1m: normalise("/api/component/gainers-table-1min"),
  gainers3m: normalise("/api/component/gainers-table"),
  losers3m: normalise("/api/component/losers-table"),
  vol1h: normalise("/api/component/banner-volume-1h"),
  health: normalise("/api/health"),
  topMoversBar: normalise("/api/component/top-movers-bar"),
  alertsRecent: (limit = 25) => normalise(`/api/alerts/recent?limit=${limit}`),
  metrics: normalise("/api/metrics"),
};

export async function fetchJson<T = any>(
  url: string,
  init: RequestInit = {},
  ms = 9000,
): Promise<T> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), ms);
  try {
    const target = normalise(url);
    const res = await fetch(target, {
      credentials: init.credentials ?? "same-origin",
      headers: {
        accept: "application/json",
        ...(init.headers || {}),
      },
      ...init,
      signal: controller.signal,
    });
    if (!res.ok) {
      const text = await res.text().catch(() => "");
      const suffix = text ? ` :: ${text.slice(0, 180)}` : "";
      throw new Error(`HTTP ${res.status} ${res.statusText} @ ${target}${suffix}`);
    }
    return (await res.json()) as T;
  } finally {
    clearTimeout(timeoutId);
  }
}

// Legacy helper retained for backwards compat.
export const httpGet = fetchJson;
export const fetchComponent = fetchJson;

const coerceArray = (payload: any): any[] => {
  if (Array.isArray(payload)) return payload;
  if (payload?.rows && Array.isArray(payload.rows)) return payload.rows;
  if (payload?.data && Array.isArray(payload.data)) return payload.data;
  return [];
};

export const mapRow = (row: any) => {
  if (!row) return { symbol: "N/A", price: 0, changePct: 0 };
  const symbol = String(row.ticker ?? row.symbol ?? row.product_id ?? "")
    .replace(/-USD$/i, "")
    .toUpperCase();
  const price = Number(row.last ?? row.current_price ?? row.price ?? 0);
  const changePctRaw =
    typeof row.changePct === "number"
      ? row.changePct
      : typeof row.pct === "number"
      ? row.pct
      : typeof row.price_change_percentage_1min === "number"
      ? row.price_change_percentage_1min
      : typeof row.price_change_percentage_3min === "number"
      ? row.price_change_percentage_3min
      : typeof row.change === "number"
      ? row.change
      : 0;
  return {
    symbol,
    price,
    changePct: Number(changePctRaw) || 0,
  };
};

export const mapBanner = (row: any) => {
  if (!row) return { symbol: "N/A", price: 0, pct: 0, label: "" };
  const symbol = String(row.symbol ?? row.ticker ?? "").replace(/-USD$/i, "").toUpperCase();
  const price = Number(row.price ?? row.last ?? row.current_price ?? 0);
  const pctRaw =
    typeof row.pct === "number"
      ? row.pct
      : typeof row.changePct === "number"
      ? row.changePct
      : typeof row.change === "number"
      ? row.change
      : 0;
  return {
    symbol,
    price,
    pct: Number(pctRaw) || 0,
    label: row.label ?? row.tag ?? "",
  };
};

export const mapRows = (payload: any, transform: (item: any) => any = mapRow) =>
  coerceArray(payload).map(transform);

export const mapBanners = (payload: any) => coerceArray(payload).map(mapBanner);
