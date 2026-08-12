const KEY = "mw_coin_history_v1";
const MAX_PER_COIN = 30;
// Matches the backend's default ALERT_IMPULSE_TTL_MINUTES for legacy rows that
// predate persisted expiry metadata.
const DEFAULT_ALERT_TTL_MS = 5 * 60 * 1000;

const safeParse = (json, fallback) => {
  try {
    return JSON.parse(json);
  } catch {
    return fallback;
  }
};

const normalizeSymbol = (value) => {
  const raw = String(value || "").trim().toUpperCase();
  if (!raw) return "";
  return raw.replace(/-USD$|-USDT$|-USDC$|-PERP$/i, "");
};

const eventSymbol = (event) =>
  normalizeSymbol(
    event?.symbol ||
    event?.product_id ||
    event?.productId ||
    event?.coin ||
    event?.pair ||
    event?.asset ||
    ""
  );

const toTimestampMs = (value) => {
  if (value === null || value === undefined || value === "") return null;
  const n = Number(value);
  if (Number.isFinite(n)) {
    return n < 1e12 ? Math.round(n * 1000) : Math.round(n);
  }
  const parsed = Date.parse(String(value));
  return Number.isFinite(parsed) ? parsed : null;
};

const eventTs = (event) => {
  const value =
    event?.event_ts_ms ??
    event?.ts_ms ??
    event?.event_ts ??
    event?.ts ??
    event?.timestamp ??
    event?.time ??
    event?.created_at ??
    event?.createdAt;
  return toTimestampMs(value);
};

export function isCoinEventActive(event, nowMs = Date.now()) {
  if (!event || !Number.isFinite(Number(nowMs))) return false;

  const expiresAtMs = toTimestampMs(event?.expires_at ?? event?.expiresAt);
  if (expiresAtMs !== null) return expiresAtMs > Number(nowMs);

  const ts = eventTs(event);
  if (ts === null) return false;

  const ttlSeconds = Number(event?.ttl_seconds ?? event?.ttlSeconds);
  const ttlMs = Number.isFinite(ttlSeconds) && ttlSeconds > 0
    ? ttlSeconds * 1000
    : DEFAULT_ALERT_TTL_MS;
  return ts + ttlMs > Number(nowMs);
}

export function loadCoinHistory() {
  if (typeof window === "undefined") return {};
  return safeParse(window.localStorage.getItem(KEY) || "{}", {});
}

export function saveCoinHistory(store) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(KEY, JSON.stringify(store || {}));
}

export function upsertCoinEvents(symbol, events) {
  if (typeof window === "undefined") return;

  const incomingRaw = Array.isArray(events) ? events : [];
  if (!incomingRaw.length) return;

  const sym = normalizeSymbol(symbol) || eventSymbol(incomingRaw[0]);
  if (!sym) return;

  const incoming = incomingRaw
    .map((event) => {
      const msg = String(event?.message || event?.text || event?.title || "").trim();
      if (!msg) return null;
      const ts = eventTs(event);
      if (ts === null) return null;
      return {
        id: event?.id ?? null,
        ts,
        symbol: sym,
        type: String(event?.type || event?.type_key || event?.kind || "alert"),
        type_key: String(event?.type_key || event?.type || event?.kind || ""),
        severity: String(event?.severity || "info"),
        message: msg,
        pct: typeof event?.pct === "number" ? event.pct : null,
        url: event?.url || event?.trade_url || event?.source_url || "",
        expires_at: event?.expires_at ?? event?.expiresAt ?? null,
        ttl_seconds: Number.isFinite(Number(event?.ttl_seconds ?? event?.ttlSeconds))
          ? Number(event?.ttl_seconds ?? event?.ttlSeconds)
          : null,
      };
    })
    .filter(Boolean);

  if (!incoming.length) return;

  const store = loadCoinHistory();
  const prev = Array.isArray(store[sym]) ? store[sym] : [];
  const merged = [...incoming, ...prev].sort((a, b) => Number(b?.ts || 0) - Number(a?.ts || 0));

  const seen = new Set();
  const deduped = [];
  for (const event of merged) {
    const key = `${event?.id || ""}|${event?.ts || ""}|${event?.message || ""}`;
    if (seen.has(key)) continue;
    seen.add(key);
    deduped.push(event);
    if (deduped.length >= MAX_PER_COIN) break;
  }

  store[sym] = deduped;
  saveCoinHistory(store);
}

export function getCoinEvents(symbol, nowMs = Date.now()) {
  const sym = normalizeSymbol(symbol);
  if (!sym) return [];
  const store = loadCoinHistory();
  const stored = Array.isArray(store[sym]) ? store[sym] : [];
  const active = stored.filter((event) => isCoinEventActive(event, nowMs));
  if (active.length !== stored.length) {
    store[sym] = active;
    saveCoinHistory(store);
  }
  return active;
}
