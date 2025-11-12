export const colors = {
  gain:  '#f0a400',     // gold/orange for gainers
  loss:  '#a16dff',     // purple for losers
  text:  '#ffffff',
  dim:   'rgba(255,255,255,0.55)',
};

// Return classes the CSS styles for tint + aura selection.
export function classForDelta(pct) {
  const v = Number(pct);
  if (!Number.isFinite(v) || v === 0) return 'is-flat';
  // gainers = gold/orange, losers = purple (final mapping)
  return v > 0 ? 'is-gain' : 'is-loss';
}
// Return only the row-state class the CSS expects.
