const KEY = "mw_coin_history_v1";
const MAX_PER_COIN = 30;

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

const eventTs = (event) => {
  const value =
    event?.event_ts_ms ??
    event?.ts_ms ??
    event?.event_ts ??
    event?.ts ??
    event?.timestamp ??
    event?.time ??
    event?.created_at ??
    event?.createdAt ??
    Date.now();
  const n = Number(value);
  if (Number.isFinite(n)) {
    return n < 1e12 ? Math.round(n * 1000) : Math.round(n);
  }
  const parsed = Date.parse(String(value));
  return Number.isFinite(parsed) ? parsed : Date.now();
};

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
      return {
        id: event?.id ?? null,
        ts: eventTs(event),
        symbol: sym,
        type: String(event?.type || event?.type_key || event?.kind || "alert"),
        type_key: String(event?.type_key || event?.type || event?.kind || ""),
        severity: String(event?.severity || "info"),
        message: msg,
        pct: typeof event?.pct === "number" ? event.pct : null,
        url: event?.url || event?.trade_url || event?.source_url || "",
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

export function getCoinEvents(symbol) {
  const sym = normalizeSymbol(symbol);
  if (!sym) return [];
  const store = loadCoinHistory();
  return Array.isArray(store[sym]) ? store[sym] : [];
}
