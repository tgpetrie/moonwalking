// Utility helpers for sanitizing numeric fields that the UI treats as baseline data.
export function toFiniteNumber(x) {
  const n = typeof x === "string" ? Number(x) : x;
  return Number.isFinite(n) ? n : null;
}

// Treat 0 or negative values as missing baselines.
export function baselineOrNull(x) {
  const n = toFiniteNumber(x);
  return n && n > 0 ? n : null;
}

// Normalize percent inputs (strings with percent signs, decimals, etc.).
export function percentOrNull(x) {
  const n = toFiniteNumber(x);
  return n === null ? null : n;
}

export function displayOrDash(x, formatter = String) {
  return x === null || x === undefined ? "—" : formatter(x);
}
