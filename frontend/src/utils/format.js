// frontend/src/utils/format.js

// Smart price formatting with flexible decimals
export function formatPrice(n, opts = {}) {
  const { fallback = "—" } = opts;
  const x = Number(n);
  if (!Number.isFinite(x)) return fallback;
  const abs = Math.abs(x);
  const sign = x < 0 ? "-" : "";

  // Big numbers: keep it tight
  if (abs >= 100) {
    return `${sign}$${abs.toFixed(2).replace(/\.00$/, "")}`;
  }

  // Mid-range: 2–4 decimals, trimmed
  if (abs >= 1) {
    return `${sign}$${abs
      .toFixed(3)
      .replace(/0+$/, "")
      .replace(/\.$/, "")}`;
  }

  if (abs >= 0.01) {
    return `${sign}$${abs
      .toFixed(4)
      .replace(/0+$/, "")
      .replace(/\.$/, "")}`;
  }

  // Tiny coins: just give enough precision
  return `${sign}$${Number(abs).toPrecision(6)}`;
}

// Percent formatter, optional sign
export function formatPct(n, { sign = true, fallback = "—" } = {}) {
  const x = Number(n);
  if (!Number.isFinite(x)) return fallback;

  // Accept either a fractional input (0.0123 -> 1.23%) or a percent value (1.23 -> 1.23%).
  // Decide based on magnitude: if abs(x) <= 1 treat as fraction and multiply by 100,
  // otherwise assume it's already a percent value.
  const value = Math.abs(x) <= 1 ? x * 100 : x;
  const abs = Math.abs(value);

  const decimals = abs >= 1 ? 2 : 4;

  const base = value
    .toFixed(decimals)
    .replace(/0+$/, "")
    .replace(/\.$/, "");

  const prefix = sign && value > 0 ? "+" : "";
  return `${prefix}${base}%`;
}

// Map delta to BHABIT palette tokens
export function colorForDelta(n) {
  const x = Number(n);
  if (!Number.isFinite(x)) return "var(--bh-neutral, #9ca3af)";

  if (x > 0) return "var(--bh-gain, #f59e0b)";   // gold/orange for gainers
  if (x < 0) return "var(--bh-loss, #a855f7)";   // purple for losers
  return "var(--bh-neutral, #9ca3af)";
}

// Shape a backend row into a 1h banner item
export function map1hPriceBannerItem(row) {
  if (!row) return null;

  const {
    symbol,
    label,
    price_now,
    price_then,
    pct_change_1h,
    delta_1h,
    pct_change,
    price,
    side,
  } = row;

  // Try the most specific fields first, then fall back
  const pct =
    pct_change_1h ??
    delta_1h ??
    pct_change ??
    null;

  const currentPrice = price_now ?? price ?? null;

  const direction =
    side ??
    (pct > 0 ? "up" : pct < 0 ? "down" : "flat");

  return {
    symbol,
    label: label || symbol,
    price: currentPrice,
    pct,
    formattedPrice: currentPrice != null
      ? formatPrice(currentPrice)
      : "—",
    formattedPct:
      pct == null ? "—" : formatPct(pct, { sign: true }),
    side: direction,
    color: colorForDelta(pct),
  };
}

// (legacy compatibility will be provided at the end of the file)

// Utility: derive a short ticker from symbol (keep existing callers happy)
export function tickerFromSymbol(sym = "") {
  if (!sym) return "";
  // Remove common suffixes and exchange markers, uppercase
  return String(sym).replace(/:.*$/, "").replace(/-(USD|USDT|PERP)$/i, "").toUpperCase();
}

// Compact number formatter used by some banners
export function formatCompact(n) {
  const v = Number(n);
  if (!Number.isFinite(v)) return "—";
  const abs = Math.abs(v);
  if (abs >= 1e9) return `${(v / 1e9).toFixed(1)}B`;
  if (abs >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
  if (abs >= 1e3) return `${(v / 1e3).toFixed(1)}K`;
  return `${Math.round(v)}`;
}

// Augment default export for compatibility
export default {
  formatPrice,
  formatPct,
  colorForDelta,
  map1hPriceBannerItem,
  tickerFromSymbol,
  formatCompact,
};
