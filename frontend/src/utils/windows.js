export const WINDOW_KEYS = Object.freeze({
  ONE_MIN: "1m",
  THREE_MIN: "3m",
  ONE_HOUR_PRICE: "1h_price",
  ONE_HOUR_VOLUME: "1h_volume",
  UNKNOWN: "unknown",
});

export const WINDOW_LABELS = Object.freeze({
  [WINDOW_KEYS.ONE_MIN]: "1m",
  [WINDOW_KEYS.THREE_MIN]: "3m",
  [WINDOW_KEYS.ONE_HOUR_PRICE]: "1h",
  [WINDOW_KEYS.ONE_HOUR_VOLUME]: "1h",
  [WINDOW_KEYS.UNKNOWN]: "",
});

const WINDOW_ALIAS_MAP = Object.freeze({
  "1m": WINDOW_KEYS.ONE_MIN,
  "3m": WINDOW_KEYS.THREE_MIN,
  "1h": WINDOW_KEYS.ONE_HOUR_PRICE,
  "1h_price": WINDOW_KEYS.ONE_HOUR_PRICE,
  "1hprice": WINDOW_KEYS.ONE_HOUR_PRICE,
  "price_1h": WINDOW_KEYS.ONE_HOUR_PRICE,
  "1h_volume": WINDOW_KEYS.ONE_HOUR_VOLUME,
  "1hvolume": WINDOW_KEYS.ONE_HOUR_VOLUME,
  "volume_1h": WINDOW_KEYS.ONE_HOUR_VOLUME,
  "vol_1h": WINDOW_KEYS.ONE_HOUR_VOLUME,
  "volume": WINDOW_KEYS.ONE_HOUR_VOLUME,
});

const normalizeToken = (raw) =>
  String(raw || "")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, "_")
    .replace(/-+/g, "_");

export const normalizeWindowKey = (raw, options = {}) => {
  const token = normalizeToken(raw);
  const typeHint = normalizeToken(options?.type || "");
  const sourceHint = normalizeToken(options?.source || "");
  const fromAlias = WINDOW_ALIAS_MAP[token];
  if (fromAlias) {
    if (
      fromAlias === WINDOW_KEYS.ONE_HOUR_PRICE &&
      (typeHint.includes("volume") || sourceHint.includes("volume"))
    ) {
      return WINDOW_KEYS.ONE_HOUR_VOLUME;
    }
    return fromAlias;
  }

  if (token === "5m" || token === "15m") return WINDOW_KEYS.THREE_MIN;
  if (typeHint.includes("1m")) return WINDOW_KEYS.ONE_MIN;
  if (typeHint.includes("3m")) return WINDOW_KEYS.THREE_MIN;
  if (typeHint.includes("volume") || sourceHint.includes("volume")) return WINDOW_KEYS.ONE_HOUR_VOLUME;
  if (typeHint.includes("1h") || sourceHint.includes("1h")) return WINDOW_KEYS.ONE_HOUR_PRICE;
  return WINDOW_KEYS.UNKNOWN;
};

export const toWindowLabel = (raw, options = {}) => {
  const key = normalizeWindowKey(raw, options);
  return WINDOW_LABELS[key] || "";
};

