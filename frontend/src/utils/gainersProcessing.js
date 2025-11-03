/**
 * Compute top gainers with optional merging of previous positive movers.
 * @param {Array} latestRaw - Raw array from backend / WS.
 * @param {Array} prev - Previous combined list (already ranked).
 * @param {Object} opts
 * @param {number} [opts.limit=20] - Max rows.
 * @param {boolean} [opts.mergePrev=true] - Whether to merge previous positive movers.
 * @param {boolean} [opts.fillMissing=true] - Use previous entry to fill missing peakCount or price when symbol repeats.
 * @returns {{combined:Array,nextPrev:Array}}
 */
 
import formatSymbol from '../lib/format.js';

export function computeTop20Gainers(latestRaw, prev = [], opts = {}) {
  const { limit = 20, mergePrev = true, fillMissing = true } = opts;
  if (!Array.isArray(latestRaw) || latestRaw.length === 0) {
    return { combined: (prev || []).slice(0, limit), nextPrev: prev };
  }

  const prevMap = (fillMissing && Array.isArray(prev) && prev.length)
    ? new Map(prev.filter(p => p && p.symbol).map(p => [formatSymbol(p.symbol), p]))
    : null;

  const take = Math.min(latestRaw.length, limit);
  const mapped = [];
  for (let i = 0; i < take; i++) {
    const item = latestRaw[i];
    if (!item) {
      continue;
    }
  const symbol = formatSymbol(item.symbol) || 'N/A';
    const base = prevMap ? prevMap.get(symbol) : undefined;
    const price = item.current_price ?? item.price ?? (base ? base.price : 0);
    const change = item.peak_gain ?? item.price_change_percentage_1min ?? item.change ?? (base ? base.change : 0);
    let peakCount;
    if (typeof item.peak_count === 'number') {
      peakCount = item.peak_count;
    } else if (typeof item.trend_streak === 'number') {
      peakCount = item.trend_streak;
    } else if (fillMissing && base) {
      peakCount = base.peakCount || 0;
    } else {
      peakCount = 0;
    }
    mapped.push({ rank: item.rank || (i + 1), symbol, price, change, peakCount });
  }

  if (mergePrev && Array.isArray(prev) && prev.length) {
    for (const p of prev) {
      if (!p || p.change <= 0) {
        continue;
      }
      if (!mapped.some(m => m.symbol === p.symbol)) {
        mapped.push(p);
      }
    }
  }

  const combined = mapped
    .sort((a, b) => (b.change || 0) - (a.change || 0))
    .slice(0, limit)
    .map((r, i) => ({ ...r, rank: i + 1 }));
  return { combined, nextPrev: combined };
}

// Small helper for tests / debugging to create mock entries
export function mockGainer(symbol, change, extra = {}) {
  return { symbol, change, price: extra.price ?? 1, peak_gain: change, peakCount: extra.peakCount ?? 0, ...extra };
}
