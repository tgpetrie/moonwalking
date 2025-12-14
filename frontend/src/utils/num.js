// Numeric utilities shared across multiple components.
export function baselineOrNull(x) {
  const n = Number(x);
  return Number.isFinite(n) && n > 0 ? n : null;
}

export function displayOrDash(x, formatter = (value) => value) {
  return x == null ? "—" : formatter(x);
}
