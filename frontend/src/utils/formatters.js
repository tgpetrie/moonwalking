export const fmt = {
  price(v) {
    if (v === 0 || v == null) return "0";
    const a = Math.abs(Number(v));
    if (a >= 1000) return Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 });
    if (a >= 10) return Number(v).toLocaleString(undefined, { maximumFractionDigits: 2 });
    if (a >= 1) return Number(v).toLocaleString(undefined, { maximumFractionDigits: 3 });
    if (a >= 0.1) return Number(v).toLocaleString(undefined, { maximumFractionDigits: 4 });
    if (a >= 0.01) return Number(v).toLocaleString(undefined, { maximumFractionDigits: 5 });
    return Number(v).toLocaleString(undefined, { maximumFractionDigits: 8 });
  },
  pct(v) {
    if (v == null || Number.isNaN(Number(v))) return "0%";
    const n = Number(v);
    const sign = n >= 0 ? "+" : "";
    const abs = Math.abs(n);
    const places = abs < 0.001 ? 3 : abs < 0.01 ? 3 : 2;
    return `${sign}${(n * 100).toFixed(places)}%`;
  },
  vol(v) {
    if (v == null) return "0";
    const n = Number(v);
    const a = Math.abs(n);
    if (a >= 1e9) return (n / 1e9).toFixed(2) + "B";
    if (a >= 1e6) return (n / 1e6).toFixed(2) + "M";
    if (a >= 1e3) return (n / 1e3).toFixed(2) + "k";
    return String(Math.round(n));
  },
};
export function formatSymbol(raw = "") {
  return raw.replace(/[-/](USDT?|USD)$/i, "").toUpperCase();
}

export function smartPrice(n) {
  if (n == null || n === "") return "";
  const num = Number(n);
  if (Number.isNaN(num)) return n;

  if (num >= 1000) return num.toLocaleString();
  if (num >= 100) return num.toFixed(0);
  if (num >= 10) return num.toFixed(2);
  if (num >= 1) return num.toFixed(3);
  if (num >= 0.01) return num.toFixed(4);
  return num.toFixed(6);
}
// frontend/src/utils/formatters.js
// ---- Rule-based precision system & registry ----

export const DEFAULT_PRECISION_RULES = [
  { min: 1, maxFrac: 2 },
  { min: 0.1, maxFrac: 4 },
  { min: 0.01, maxFrac: 5 },
  { min: 0.001, maxFrac: 6 },
  { min: 0.0001, maxFrac: 8 },
  { min: 0.00001, maxFrac: 9 },
  { min: 0.000001, maxFrac: 10 }
  // anything smaller uses scientific notation
];

const PLACEHOLDER = '—';

// Mutable (by design) registry to allow runtime overrides (theme/localization)
export const formatterRegistry = {
  locale: 'en-US',
  currency: 'USD',
  precisionRules: DEFAULT_PRECISION_RULES,
  scientificSigFigs: 2,
  minScientific: 1e-6, // below smallest explicit rule threshold
  set(partial) { Object.assign(this, partial); }
};

const trimZeros = (str) => str.replace(/\.([0-9]*?)0+$/,(m, g1)=> g1.length ? '.'+g1 : '').replace(/\.$/,'');

function chooseRule(abs, rules) {
  for (const r of rules) {
    if (abs >= r.min) return r;
  }
  return null;
}

export function formatCurrency(value, { currency = formatterRegistry.currency, compact = false, locale = formatterRegistry.locale, rules = formatterRegistry.precisionRules, trim = false, sign = false } = {}) {
  const n = Number(value);
  if (!Number.isFinite(n)) return PLACEHOLDER;
  const negative = n < 0;
  const abs = Math.abs(n);
  const rule = chooseRule(abs, rules);
  let formatted;
  if (compact) {
    try {
  // Use compact Intl to format the absolute number, then prepend symbol and sign
  const intl = new Intl.NumberFormat(locale, { notation: 'compact', maximumFractionDigits: (rule?.maxFrac ?? 2) });
  const compactNum = intl.format(Math.abs(n));
  const signed = negative ? '-' : (sign && !negative ? '+' : '');
  const symbol = currency === 'USD' ? '$' : '';
      if (symbol) {
        return `${symbol}${signed}${compactNum}`;
      }
      return `${signed}${compactNum} ${currency}`.trim();
    } catch (_e) { /* fallback below */ }
  }
  if (rule) {
    formatted = abs.toFixed(rule.maxFrac);
  } else {
    // Very small -> scientific
    formatted = abs.toExponential(formatterRegistry.scientificSigFigs);
  }
  if (trim && rule) {
    formatted = trimZeros(formatted);
  }
  // Build currency string manually (keeps consistency across environments)
  const symbol = currency === 'USD' ? '$' : '';
  const signed = negative ? '-' : (sign && !negative ? '+' : '');
  // Place currency symbol first, then sign, then number (matches legacy expectations)
  if (symbol) {
    return `${symbol}${negative ? '-' : (sign && !negative ? '+' : '')}${formatted}`;
  }
  return `${negative ? '-' : (sign && !negative ? '+' : '')}${formatted} ${currency}`.trim();
}

export function formatPercent(value, { fromFraction = true, max = 4, trim = true, sign = true, locale = formatterRegistry.locale } = {}) {
  const n = Number(value);
  if (!Number.isFinite(n)) {
    return PLACEHOLDER;
  }
  const pct = fromFraction ? n * 100 : n;
  const negative = pct < 0;
  let formatted;
  try {
    const intl = new Intl.NumberFormat(locale, { maximumFractionDigits: max, minimumFractionDigits: 0 });
    // Format absolute value, we'll add sign manually to avoid duplicate signs
    formatted = intl.format(Math.abs(pct));
  } catch (_e) {
    formatted = Math.abs(pct).toFixed(max);
  }
  if (trim) {
    formatted = trimZeros(formatted);
  }
  const s = negative ? '-' : (sign && pct > 0 ? '+' : '');
  return `${s}${formatted}%`;
}

// Backward compatible wrappers (deprecated) -------------------------
export const formatPrice = (price) => formatCurrency(price, { currency: formatterRegistry.currency });

export const formatPercentage = (
  value,
  { decimals = 4, sign = false, fraction = false } = {}
) => {
  const n = Number(value);
  if (!Number.isFinite(n)) {
    return '—';
  }
  const pct = fraction ? n * 100 : n; // set fraction:true if your data is 0..1
  const s = sign && pct > 0 ? '+' : '';
  return `${s}${pct.toFixed(decimals)}%`;
};

// Shorten long token symbols/names to avoid layout breaks.
// Example: 'BITCOIN' -> 'BITCO…' when maxLen=6
export const truncateSymbol = (text, maxLen = 6) => {
  if (typeof text !== 'string') {
    return String(text ?? '');
  }
  if (text.length <= maxLen) {
    return text;
  }
  if (maxLen <= 1) {
    return text.slice(0, maxLen);
  }
  return text.slice(0, maxLen - 1) + '…';
};

// Export an aggregate for potential future theming/DI
export const formatters = {
  formatCurrency,
  formatPercent,
  formatPrice, // legacy
  formatPercentage, // legacy
  truncateSymbol,
  registry: formatterRegistry
};
