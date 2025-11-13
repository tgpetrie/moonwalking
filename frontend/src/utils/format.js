// Formatting + adapters shared by tables & banners.

// --- symbol helpers ---
export function tickerFromSymbol(sym) {
  if (typeof sym !== "string") return "";
  return sym.trim().replace(/-USD$/i, "");
}

// --- number guards ---
export function toNum(v, fallback = 0) {
  const n = Number(v);
  return Number.isFinite(n) ? n : fallback;
}

// --- price formatting ---
export function formatPrice(n, opts = {}) {
  const val = toNum(n, 0);
  const { min = 2, max = 2 } = opts;
  if (val >= 1000) return val.toFixed(0);
  if (val >= 100) return val.toFixed(Math.max(0, Math.min(max, 1)));
  if (val >= 1) return val.toFixed(Math.max(min, 2));
  return val.toFixed(Math.max(max, 6));
}

// --- percentage formatting ---
export function formatPct(n, { sign = true } = {}) {
  const val = toNum(n, 0) * 100; // backend sends decimal fraction (0.0158 -> 1.58%)
  const abs = Math.abs(val);
  let digits = 2;
  if (abs >= 100) digits = 0;
  else if (abs >= 10) digits = 1;
  const core = abs.toFixed(digits);
  return (sign ? (val >= 0 ? "+" : "−") : "") + core + "%";
}

// --- compact formatting ---
export function formatCompact(n) {
  const val = toNum(n, 0);
  const abs = Math.abs(val);
  if (abs >= 1e9) return (val / 1e9).toFixed(1) + "B";
  if (abs >= 1e6) return (val / 1e6).toFixed(1) + "M";
  if (abs >= 1e3) return (val / 1e3).toFixed(1) + "K";
  return val.toFixed(0);
}

// --- previous price (1m/3m) ---
export function resolvePrevPrice(row, window = "1m") {
  if (!row || typeof row !== "object") return null;
  const w = String(window).toLowerCase();
  const cands = w.startsWith("1")
    ? [row.initial_price_1min, row.prev_1m, row.previous_1m, row.initial_1min]
    : [row.initial_price_3min, row.prev_3m, row.previous_3m, row.initial_3min];
  for (const c of cands) {
    const n = Number(c);
    if (Number.isFinite(n)) return n;
  }
  return null;
}

// --- 1h volume change ---
export function calcVolumeChange1h(a, b) {
  if (arguments.length === 1 && a && typeof a === "object") {
    const row = a;
    const curr = toNum(row.volume_1h ?? row.volume_abs ?? row.volume, 0);
    const prev = toNum(row.volume_1h_prev ?? row.prev_volume_1h ?? row.volume_prev, 0);
    return calcVolumeChange1h(curr, prev);
  }
  const curr = toNum(a, 0);
  const prev = toNum(b, 0);
  const diff = curr - prev;
  const pct = prev === 0 ? 0 : (diff / prev) * 100;
  return { curr, prev, diff, pct };
}

// --- color tags (UI maps to classes) ---
export function colorForDelta(n) {
  const val = toNum(n, 0);
  if (val > 0) return "gain";   // gold/orange
  if (val < 0) return "loss";   // purple
  return "neutral";
}

// --- row adapters ---
export function map1mRow(row, idx = 0) {
  const symbol = tickerFromSymbol(row?.symbol);
  return {
    rank: row?.rank ?? idx + 1,
    symbol,
    current_price: toNum(row?.current_price ?? row?.price, 0),
    previous_price: resolvePrevPrice(row, "1m"),
    price_change_percentage_1min: toNum(row?.price_change_percentage_1min ?? row?.change1m ?? row?.change, 0),
    price_change_percentage_3min: undefined,
    isGainer: true,
  };
}

export function map3mRow(row, idx = 0, { isGainer = true } = {}) {
  const symbol = tickerFromSymbol(row?.symbol);
  return {
    rank: row?.rank ?? idx + 1,
    symbol,
    current_price: toNum(row?.current_price ?? row?.price, 0),
    previous_price: resolvePrevPrice(row, "3m"),
    price_change_percentage_1min: undefined,
    price_change_percentage_3min: toNum(row?.price_change_percentage_3min ?? row?.change3m ?? row?.change, 0),
    isGainer: !!isGainer,
  };
}

// --- banners ---
export function map1hPriceBannerItem(row) {
  return {
    symbol: tickerFromSymbol(row?.symbol),
    pct: toNum(row?.pct ?? row?.change1h ?? row?.change, 0),
    price: toNum(row?.price ?? row?.current_price, 0),
  };
}

export function map1hVolumeBannerItem(row) {
  const { curr, prev, pct } = calcVolumeChange1h(row);
  return {
    symbol: tickerFromSymbol(row?.symbol),
    volume_abs: curr,
    prev_volume_abs: prev,
    pct,
  };
}

// --- tiny helpers ---
export function safeArray(v) { return Array.isArray(v) ? v : []; }
export function nonEmptyString(v, fb = "") { return (typeof v === "string" && v.trim()) ? v.trim() : fb; }

export default {
  tickerFromSymbol, toNum,
  formatPrice, formatPct, formatCompact,
  resolvePrevPrice, calcVolumeChange1h,
  colorForDelta,
  map1mRow, map3mRow,
  map1hPriceBannerItem, map1hVolumeBannerItem,
  safeArray, nonEmptyString,
};
