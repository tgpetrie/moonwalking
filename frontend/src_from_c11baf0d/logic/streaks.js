// Minute-based presence tracker for rows staying in "top" tables.
// API: updateStreaks(timeframe, rows) -> get(symbol) => { level }
// - timeframe: any string key (e.g., '1m', '3m')
// - rows: array of objects with at least { symbol }
// Semantics:
//   - Track consecutive minutes a symbol remains present.
//   - Do not show anything until the symbol has been present for > 2 minutes.
//   - Display level = minutes_present - 1. Example: 3 minutes -> level 2 => "Px2".

const state = new Map(); // timeframe -> Map(symbol -> { minutes, lastSeen, lastInc })
const STEP_MS = 60_000; // one minute increments
const MAX_MINUTES = 99; // cap to avoid unbounded growth

export function updateStreaks(timeframe, rows = []) {
  if (!state.has(timeframe)) state.set(timeframe, new Map());
  const m = state.get(timeframe);
  const now = Date.now();
  const current = new Set();

  // Mark current rows and advance minute counters when a full minute elapses
  for (const r of rows) {
    const sym = r && r.symbol;
    if (!sym) continue;
    current.add(sym);
    const entry = m.get(sym) || { minutes: 0, lastSeen: 0, lastInc: 0 };
    entry.lastSeen = now;
    if (entry.lastInc === 0) {
      // first sighting starts minute window
      entry.lastInc = now;
      entry.minutes = Math.max(1, entry.minutes || 1);
    } else if (now - entry.lastInc >= STEP_MS) {
      // advance by whole minutes elapsed
      const steps = Math.floor((now - entry.lastInc) / STEP_MS);
      entry.minutes = Math.min(MAX_MINUTES, entry.minutes + steps);
      entry.lastInc += steps * STEP_MS;
    }
    m.set(sym, entry);
  }

  // Reset symbols not present this tick
  for (const [sym, entry] of m.entries()) {
    if (!current.has(sym)) {
      m.set(sym, { minutes: 0, lastSeen: 0, lastInc: 0 });
    }
  }

  // Return accessor with display mapping
  return function get(symbol) {
    const e = m.get(symbol) || { minutes: 0 };
    const minutes = e.minutes || 0;
    const level = minutes > 2 ? minutes - 1 : 0; // show only after >2 minutes
    return { level, minutes };
  };
}

export default { updateStreaks };
