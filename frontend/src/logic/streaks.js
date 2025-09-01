// Lightweight client-side streak tracker for table rows.
// API: updateStreaks(timeframe, rows) -> get(symbol) => { level }
// - timeframe: '1m' | '3m' (string key)
// - rows: array of objects with at least { symbol }
// Level semantics:
//   0 = no streak present
//   1 = present this tick
//   2..N = consecutive ticks present (capped)

const MAX_LEVEL = 9;
const state = new Map(); // timeframe -> Map(symbol -> level)

export function updateStreaks(timeframe, rows = []) {
  if (!state.has(timeframe)) state.set(timeframe, new Map());
  const m = state.get(timeframe);

  const current = new Set();
  for (const r of rows) {
    const sym = r && r.symbol;
    if (!sym) continue;
    current.add(sym);
    const prev = m.get(sym) || 0;
    m.set(sym, Math.min(MAX_LEVEL, prev + 1));
  }
  // Decay or reset symbols that dropped out this tick
  for (const [sym, lvl] of m.entries()) {
    if (!current.has(sym)) {
      // simple reset; could decay by 1 if preferred
      m.set(sym, 0);
    }
  }
  return function get(symbol) {
    return { level: m.get(symbol) || 0 };
  };
}

export default { updateStreaks };

