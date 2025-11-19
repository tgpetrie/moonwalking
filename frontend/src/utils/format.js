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

  // Backend already returns **percent values** (e.g., 2.53 === 2.53%).
  // We no longer try to guess between fraction vs. percent; treat the
  // input as a percent unit and only control decimals + sign.
  const value = x;
  const abs = Math.abs(value);

  // Canonical rules (see UI_HOME_DASHBOARD.md):
  // - abs(change) < 1  → 3 decimals
  // - abs(change) >= 1 → 2 decimals
  const decimals = abs < 1 ? 3 : 2;

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

// Simple 1h price banner mapper: symbol, current price, pct change, gain/loss
export function map1hPriceBannerItemBase(raw) {
  if (!raw) return null;

  const symbol = raw.symbol || raw.ticker || "";

  const current =
    raw.current_price ??
    raw.price_now ??
    raw.price ??
    raw.last_price ??
    null;

  const pctRaw =
    raw.pct_change_1h ??
    raw.price_change_percentage_1h ??
    raw.change_1h_price ??
    raw.delta_1h ??
    raw.change_1h ??
    raw.pct_change ??
    0;

  const pct = Number(pctRaw);
  const pctChange = Number.isFinite(pct) ? pct : 0;

  return {
    symbol,
    currentPrice: current,
    pctChange,
    isGain: pctChange > 0,
    isLoss: pctChange < 0,
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

// Simple 1h volume banner mapper: symbol, current volume, pct change
export function map1hVolumeBannerItemBase(raw) {
  if (!raw) return null;

  const symbol = raw.symbol || raw.ticker || "";

  const current =
    raw.volume_1h ??
    raw.volume ??
    raw.current_volume ??
    null;

  const pctRaw =
    raw.volume_change_1h ??
    raw.volume_change_pct_1h ??
    raw.volume_change_pct ??
    raw.change_1h_volume ??
    raw.change_vol_1h ??
    0;

  const pct = Number(pctRaw);
  const pctChange = Number.isFinite(pct) ? pct : 0;

  return {
    symbol,
    currentVolume: current,
    pctChange,
    isGain: pctChange > 0,
    isLoss: pctChange < 0,
  };
}

// Augment default export for compatibility
export default {
  formatPrice,
  formatPct,
  colorForDelta,
  map1hPriceBannerItemBase,
  map1hVolumeBannerItemBase,
  tickerFromSymbol,
  formatCompact,
};
