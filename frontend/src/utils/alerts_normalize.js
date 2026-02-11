import { WINDOW_KEYS, normalizeWindowKey, toWindowLabel } from "./windows.js";

const WINDOW_RE = /\b(1m|3m|1h|5m|15m)\b/i;
const TYPE_WINDOW_RE = /(?:_|\b)(1M|3M|5M|15M|1H)(?:\b|_)/i;
const PCT_RE = /([+-]?\d+(?:\.\d+)?)\s*%/;

export const TYPE_KEYS = {
  moonshot: "moonshot",
  crater: "crater",
  breakout: "breakout",
  dump: "dump",
  move: "move",
  whale: "whale",
  stealth: "stealth",
  divergence: "divergence",
  fomo: "fomo",
  fear: "fear",
  sentiment: "sentiment",
  volume: "volume",
  unknown: "unknown",
};

export const TYPE_TEXT = {
  moonshot: "MOONSHOT",
  crater: "CRATER",
  breakout: "BREAKOUT",
  dump: "DUMP",
  move: "MOVE",
  whale: "WHALE",
  stealth: "STEALTH",
  divergence: "DIVERGENCE",
  fomo: "FOMO",
  fear: "FEAR",
  sentiment: "SENTIMENT",
  volume: "VOLUME",
  unknown: "ALERT",
};

export const TYPE_EMOJI = {
  moonshot: "🚀",
  crater: "🕳️",
  breakout: "📈",
  dump: "📉",
  move: "⚡",
  whale: "🐋",
  stealth: "🕵️",
  divergence: "⚖️",
  fomo: "🔥",
  fear: "🧊",
  sentiment: "🌊",
  volume: "📊",
  unknown: "🔔",
};

const toNumber = (value) => {
  if (value == null) return null;
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  const s = String(value).trim();
  if (!s) return null;
  const cleaned = s.replace(/[%+,]/g, "");
  const n = Number(cleaned);
  return Number.isFinite(n) ? n : null;
};

const firstNumber = (...values) => {
  for (const value of values) {
    const n = toNumber(value);
    if (Number.isFinite(n)) return n;
  }
  return null;
};

const normalizeSeverity = (value) => {
  const s = String(value || "").trim().toLowerCase();
  if (["critical", "high", "medium", "low", "info"].includes(s)) return s;
  return "info";
};

const normalizeSymbol = (value) => {
  const raw = String(value || "").trim().toUpperCase();
  if (!raw) return "";
  return raw.replace(/-USD$|-USDT$|-PERP$/i, "");
};

const normalizeProductId = (value) => {
  const raw = String(value || "").trim().toUpperCase();
  if (!raw) return "";
  return raw.includes("-") ? raw : `${raw}-USD`;
};

const typeWindow = (rawType) => {
  const t = String(rawType || "");
  const m = t.match(TYPE_WINDOW_RE);
  if (!m) return "";
  return m[1].toLowerCase();
};

export const extractWindow = (raw) => {
  const s = String(raw || "");
  if (!s) return "";
  const m = s.match(WINDOW_RE);
  if (!m) return "";
  return toWindowLabel(m[1].toLowerCase());
};

export const extractPct = (raw) => {
  const s = String(raw || "");
  if (!s) return null;
  const m = s.match(PCT_RE);
  if (!m) return null;
  const n = Number(m[1]);
  return Number.isFinite(n) ? n : null;
};

const mapTypeKey = (rawType) => {
  const t = String(rawType || "").toLowerCase();
  if (!t) return "";
  if (t.includes("moonshot")) return TYPE_KEYS.moonshot;
  if (t.includes("crater")) return TYPE_KEYS.crater;
  if (t.includes("breakout")) return TYPE_KEYS.breakout;
  if (t.includes("dump")) return TYPE_KEYS.dump;
  if (t.includes("whale")) return TYPE_KEYS.whale;
  if (t.includes("stealth")) return TYPE_KEYS.stealth;
  if (t.includes("diverg")) return TYPE_KEYS.divergence;
  if (t.includes("fomo")) return TYPE_KEYS.fomo;
  if (t.includes("fear")) return TYPE_KEYS.fear;
  if (t.includes("sentiment")) return TYPE_KEYS.sentiment;
  if (t.includes("volume")) return TYPE_KEYS.volume;
  if (t.includes("impulse")) return ""; // classify by thresholds
  return "";
};

const inferDirection = ({ rawDirection, pct }) => {
  const raw = String(rawDirection || "").toLowerCase();
  if (["up", "down", "flat", "reversal_up", "reversal_down", "accumulation", "distribution"].includes(raw)) {
    return raw;
  }
  if (!Number.isFinite(pct)) return "flat";
  if (pct > 0) return "up";
  if (pct < 0) return "down";
  return "flat";
};

export const parseAlertCore = (a = {}) => {
  const msg = String(a?.message || "");
  const title = String(a?.title || "");
  const type = String(a?.type || a?.alert_type || "");

  const symbolRaw =
    a?.product_id ||
    a?.symbol ||
    a?.pair ||
    a?.ticker ||
    a?.market ||
    "";

  const explicitWindowRaw =
    String(a?.window || a?.window_label || a?.meta?.window || a?.evidence?.window || "").trim().toLowerCase();

  const windowRaw =
    explicitWindowRaw ||
    typeWindow(type) ||
    extractWindow(type) ||
    extractWindow(msg) ||
    extractWindow(title) ||
    "";

  const windowKey = normalizeWindowKey(windowRaw, { type });
  const window = windowKey === WINDOW_KEYS.UNKNOWN ? "" : toWindowLabel(windowKey);

  let pct = firstNumber(
    a?.pct,
    a?.change_pct,
    a?.percent_change,
    a?.price_change_pct,
    a?.price_change_percentage,
    a?.price_change_percentage_1min,
    a?.price_change_percentage_3min,
    a?.meta?.pct,
    a?.meta?.percent_change,
    a?.evidence?.pct,
    a?.evidence?.pct_1m,
    a?.evidence?.pct_3m,
    a?.evidence?.pct_1h,
    a?.ret_1m,
    a?.ret_3m
  );

  if (!Number.isFinite(pct)) {
    pct = extractPct(msg);
  }
  if (!Number.isFinite(pct)) {
    pct = extractPct(title);
  }

  return {
    symbol: String(symbolRaw || "").trim(),
    windowKey,
    window,
    pct: Number.isFinite(pct) ? pct : null,
  };
};

export const classifyByThreshold = ({ window, windowKey, pct }) => {
  if (!Number.isFinite(pct)) {
    return { type_key: TYPE_KEYS.unknown, severity: "info" };
  }

  const w =
    windowKey ||
    normalizeWindowKey(window, { source: "price" }) ||
    WINDOW_KEYS.THREE_MIN;
  const p = pct;

  if (w === WINDOW_KEYS.ONE_MIN) {
    if (p >= 12) return { type_key: TYPE_KEYS.moonshot, severity: "critical" };
    if (p >= 8) return { type_key: TYPE_KEYS.moonshot, severity: "high" };
    if (p >= 4) return { type_key: TYPE_KEYS.breakout, severity: "medium" };
    if (p >= 2) return { type_key: TYPE_KEYS.move, severity: "low" };
    if (p > -4) return { type_key: TYPE_KEYS.move, severity: "info" };
    if (p >= -8) return { type_key: TYPE_KEYS.dump, severity: "medium" };
    if (p >= -12) return { type_key: TYPE_KEYS.crater, severity: "high" };
    return { type_key: TYPE_KEYS.crater, severity: "critical" };
  }

  if (w === WINDOW_KEYS.ONE_HOUR_PRICE || w === WINDOW_KEYS.ONE_HOUR_VOLUME) {
    if (p >= 8) return { type_key: TYPE_KEYS.breakout, severity: "high" };
    if (p >= 4) return { type_key: TYPE_KEYS.move, severity: "medium" };
    if (p <= -8) return { type_key: TYPE_KEYS.dump, severity: "high" };
    if (p <= -4) return { type_key: TYPE_KEYS.dump, severity: "medium" };
    return { type_key: TYPE_KEYS.move, severity: "low" };
  }

  if (p >= 18) return { type_key: TYPE_KEYS.moonshot, severity: "critical" };
  if (p >= 12) return { type_key: TYPE_KEYS.moonshot, severity: "high" };
  if (p >= 6) return { type_key: TYPE_KEYS.breakout, severity: "medium" };
  if (p >= 3) return { type_key: TYPE_KEYS.move, severity: "low" };
  if (p <= -12) return { type_key: TYPE_KEYS.crater, severity: "critical" };
  if (p <= -6) return { type_key: TYPE_KEYS.crater, severity: "high" };
  if (p <= -3) return { type_key: TYPE_KEYS.dump, severity: "medium" };
  return { type_key: TYPE_KEYS.move, severity: "info" };
};

export const formatAlertTitle = ({ symbol, pct, window, type_key }) => {
  const key = TYPE_TEXT[type_key] ? type_key : TYPE_KEYS.unknown;
  const emoji = TYPE_EMOJI[key] || TYPE_EMOJI.unknown;
  const label = TYPE_TEXT[key] || TYPE_TEXT.unknown;
  const sym = symbol || "UNKNOWN";
  const pctText = Number.isFinite(pct) ? `${pct > 0 ? "+" : ""}${pct.toFixed(2)}%` : "";
  const winText = window ? ` / ${window}` : "";
  const tail = [sym, pctText].filter(Boolean).join(" ");
  return `${emoji} ${label}${tail ? ` - ${tail}` : ""}${winText}`.trim();
};

export const normalizeAlert = (a = {}) => {
  const core = parseAlertCore(a);
  const rawType = String(a?.type || a?.alert_type || "");
  const mappedType = mapTypeKey(rawType);
  const thresholdType = classifyByThreshold({
    window: core.window,
    windowKey: core.windowKey,
    pct: core.pct,
  });

  const type_key = mappedType || thresholdType.type_key || TYPE_KEYS.unknown;
  const severity = normalizeSeverity(a?.severity || a?.sev || thresholdType.severity);
  const symbol = normalizeSymbol(core.symbol);
  const product_id = normalizeProductId(a?.product_id || core.symbol || symbol);
  const direction = inferDirection({
    rawDirection: a?.direction || a?.meta?.direction || a?.evidence?.direction,
    pct: core.pct,
  });

  const out = {
    ...a,
    symbol,
    product_id,
    window_key: core.windowKey,
    window: core.window || "",
    pct: Number.isFinite(core.pct) ? core.pct : null,
    type_key,
    severity,
    direction,
  };

  if (!String(out.title || "").trim()) {
    out.title = formatAlertTitle(out);
  }

  return out;
};

export const typeKeyToUpper = (typeKey) => {
  const k = String(typeKey || "").toLowerCase();
  return TYPE_TEXT[k] || TYPE_TEXT.unknown;
};
