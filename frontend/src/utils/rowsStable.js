// Utilities to maintain stable object identity for rows to reduce React re-renders

/** Compare two row objects shallowly by symbol + core numeric fields */
export function rowsEqual(a, b) {
  if (a === b) return true;
  if (!a || !b) return false;
  return a.symbol === b.symbol && a.price === b.price && a.change === b.change && a.change3m === b.change3m && a.peakCount === b.peakCount && a.rank === b.rank;
}

/**
 * Reconcile a new list of plain row objects with a previous list, reusing
 * existing object references where contents are unchanged.
 * @param {Array} nextRaw - new normalized rows (rank already assigned)
 * @param {Array} prev - previous rendered list
 * @returns {Array} reconciled array with maximal reuse
 */
export function reconcileRows(nextRaw, prev) {
  if (!Array.isArray(nextRaw) || nextRaw.length === 0) return [];
  if (!Array.isArray(prev) || prev.length === 0) return nextRaw.slice();

  const prevMap = new Map();
  for (let i = 0; i < prev.length; i++) {
    const r = prev[i];
    if (r && r.symbol) prevMap.set(r.symbol, r);
  }
  const out = new Array(nextRaw.length);
  for (let i = 0; i < nextRaw.length; i++) {
    const n = nextRaw[i];
    const prevMatch = prevMap.get(n.symbol);
    if (prevMatch && rowsEqual(prevMatch, n)) {
      out[i] = prevMatch; // reuse reference
    } else {
      out[i] = n;
    }
  }
  return out;
}

/** During idle time prune any large arrays to the limit (in-place mutation avoided) */
export function trimList(list, limit = 50) {
  if (!Array.isArray(list) || list.length <= limit) return list;
  return list.slice(0, limit);
}