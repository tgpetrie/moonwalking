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
export function computeTop20Gainers(latestRaw, prev = [], opts = {}) {
  const { limit = 20, mergePrev = true, fillMissing = true } = opts;
  if (!Array.isArray(latestRaw) || latestRaw.length === 0) {
    return { combined: (prev || []).slice(0, limit), nextPrev: prev };
  }

  const prevMap = (fillMissing && Array.isArray(prev) && prev.length)
    ? new Map(prev.filter(p => p && p.symbol).map(p => [p.symbol, p]))
    : null;

  // Normalize incoming entries
  function normalizeEntries(arr) {
    return (Array.isArray(arr) ? arr : [])
      .filter(Boolean)
      .map((item, idx) => {
        const symbol = item.symbol?.replace('-USD', '') || 'N/A';
        const base = prevMap ? prevMap.get(symbol) : undefined;
        const price = item.current_price ?? item.price ?? (base ? base.price : 0);
        const rawChange = item.peak_gain ?? item.price_change_percentage_1min ?? item.change ?? (base ? base.change : 0);
        const change = (typeof rawChange === 'number' && !Number.isNaN(rawChange)) ? Number(rawChange) : 0;
        const peakCount = (typeof item.peak_count === 'number')
          ? item.peak_count
          : (typeof item.trend_streak === 'number' ? item.trend_streak : (fillMissing && base ? (base.peakCount || 0) : 0));
        return { symbol, price, change, peakCount, srcIndex: idx, rank: item.rank || (idx + 1) };
      });
  }

  const mappedAll = normalizeEntries(latestRaw);

  // If too few entries, include previous positive movers to keep list full
  const mapped = mappedAll.slice();
  if (mergePrev && Array.isArray(prev) && prev.length) {
    for (const p of prev) {
      if (!p || p.change <= 0) {
        continue;
      }
      if (!mapped.some((m) => m.symbol === p.symbol)) {
        mapped.push(p);
      }
    }
  }

  // Detect whether the incoming 'change' values are fractions (0..1) by median abs
  function medianAbsOf(arr) {
    const vals = arr.map(m => Math.abs(Number(m.change) || 0)).filter(Number.isFinite);
    if (!vals.length) return 0;
    const s = vals.slice().sort((a, b) => a - b);
    const mid = Math.floor(s.length / 2);
    return (s.length % 2 === 1) ? s[mid] : (s[mid - 1] + s[mid]) / 2;
  }

  const medianAbs = medianAbsOf(mapped);
  const needScale = medianAbs > 0 && medianAbs < 0.02;
  if (needScale) mapped.forEach(m => { m.change = Number(m.change) * 100; });

  // Final sort by numeric change desc and pick top limit
  const combined = mapped
    .sort((a, b) => (Number(b.change) || 0) - (Number(a.change) || 0))
    .slice(0, limit)
    .map((r, i) => ({ ...r, rank: i + 1 }));

  return { combined, nextPrev: combined };
}

// Small helper for tests / debugging to create mock entries
export function mockGainer(symbol, change, extra = {}) {
  return { symbol, change, price: extra.price ?? 1, peak_gain: change, peakCount: extra.peakCount ?? 0, ...extra };
}
