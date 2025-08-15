export const formatPrice = (price) => {
  if (!Number.isFinite(price)) return 'N/A';
  
  if (price >= 1) {
    return `$${price.toFixed(2)}`;
  } else if (price >= 0.1) {
    return `$${price.toFixed(4)}`;
  } else if (price >= 0.01) {
    return `$${price.toFixed(5)}`;
  } else if (price >= 0.001) {
    return `$${price.toFixed(6)}`;
  } else if (price >= 0.0001) {
    return `$${price.toFixed(8)}`;
  } else if (price >= 0.00001) {
    return `$${price.toFixed(9)}`;
  } else if (price >= 0.000001) {
    return `$${price.toFixed(10)}`;
  } else {
    // For extremely small values, use scientific notation but format it nicely
    const scientific = price.toExponential(2);
    return `$${scientific}`;
  }
};

export const formatPercentage = (
  value,
  { decimals = 2, sign = false, fraction = false } = {}
) => {
  const n = Number(value);
  if (!Number.isFinite(n)) return '—';
  const pct = fraction ? n * 100 : n; // set fraction:true if your data is 0..1
  const s = sign && pct > 0 ? '+' : '';
  return `${s}${pct.toFixed(decimals)}%`;
};

// Shorten long token symbols/names to avoid layout breaks.
// Example: 'BITCOIN' -> 'BITCO…' when maxLen=6
export const truncateSymbol = (text, maxLen = 6) => {
  if (typeof text !== 'string') return String(text ?? '');
  if (text.length <= maxLen) return text;
  if (maxLen <= 1) return text.slice(0, maxLen);
  return text.slice(0, maxLen - 1) + '…';
};