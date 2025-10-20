// frontend/src/lib/api.ts
// Centralised endpoint map + fetch helpers + response mappers.

export const API_BASE: string = (import.meta as any)?.env?.VITE_API_BASE || "";

const normalise = (path: string) => {
  if (!path) return path;
  if (path.startsWith("http")) return path;
  if (path.startsWith("/")) return `${API_BASE}${path}`;
  return `${API_BASE}/${path}`;
};

export async function fetchJson<T = any>(url: string, init: RequestInit = {}): Promise<T> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 9000);
  try {
    const res = await fetch(normalise(url), {
      credentials: "same-origin",
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
      throw new Error(`HTTP ${res.status} ${res.statusText} @ ${url}${suffix}`);
    }
    return (await res.json()) as T;
  } finally {
    clearTimeout(timeoutId);
  }
}

// Legacy helper retained for backwards compat.
export const httpGet = fetchJson;
export const fetchComponent = fetchJson;

export const endpoints = {
  health: normalise("/api/health"),
  gainers1m: normalise("/api/component/gainers-table-1min"),
  gainers3m: normalise("/api/component/gainers-table"),
  losers3m: normalise("/api/component/losers-table"),
  banner1h: normalise("/api/component/top-movers-bar"),
  bannerVolume1h: normalise("/api/component/banner-volume-1h"),
  topMoversBar: normalise("/api/component/top-movers-bar"),
  alertsRecent: (limit = 25) => normalise(`/api/alerts/recent?limit=${limit}`),
  metrics: normalise("/api/metrics"),
};

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
