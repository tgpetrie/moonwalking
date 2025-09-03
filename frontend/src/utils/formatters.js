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

export function formatPercent(value, { fromFraction = true, max = 2, trim = true, sign = true, locale = formatterRegistry.locale } = {}) {
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
  { decimals = 3, sign = false, fraction } = {}
) => {
  const n = Number(value);
  if (!Number.isFinite(n)) {
    return '—';
  }
  // Auto-detect whether input is a fraction (0..1) when caller doesn't specify.
  // Many data sources sometimes return 0.1234 (== 12.34%) or 12.34 (== 12.34%).
  // If `fraction` is explicitly provided, respect it; otherwise infer from magnitude.
  let isFraction;
  if (typeof fraction === 'boolean') {
    isFraction = fraction;
  } else {
    const abs = Math.abs(n);
    // Treat numbers <= 1 (and not zero) as fractions by default.
    isFraction = abs > 0 && abs <= 1;
  }
  const pct = isFraction ? n * 100 : n; // convert fraction to percent when needed
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
