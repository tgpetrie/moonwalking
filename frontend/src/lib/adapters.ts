// Adapter utilities to normalize backend row shapes into a stable frontend shape
export function normalizeBannerRow(row: any) {
  if (!row || typeof row !== 'object') return row;

  const symbolRaw = row.symbol ?? row.ticker ?? row.asset ?? '';
  const symbol = String(symbolRaw || '').toUpperCase();

  const currentPrice = row.current_price ?? row.price ?? row.last_price ?? null;
  const priceChange1h = row.price_change_1h ?? row.price_change_percentage_1h ?? row.pct_change_1h ?? row.change_pct ?? null;

  const volume24h = Number(row.volume_24h ?? row.volume ?? 0) || 0;

  let volumeChangePct: number | null = null;
  if (row.volume_change_1h_pct != null && !Number.isNaN(Number(row.volume_change_1h_pct))) {
    volumeChangePct = Number(row.volume_change_1h_pct);
  } else if (row.volume_change_estimate != null && !Number.isNaN(Number(row.volume_change_estimate))) {
    volumeChangePct = Number(row.volume_change_estimate);
  } else if (priceChange1h != null && !Number.isNaN(Number(priceChange1h))) {
    // fallback heuristic preserved from existing code: estimate from price change
    volumeChangePct = Number(priceChange1h) * 0.5;
  }

  const isEstimated = !(row.volume_change_1h_pct != null && !Number.isNaN(Number(row.volume_change_1h_pct)));

  return {
    // canonical fields used across UI
    symbol,
    originalSymbol: symbolRaw,
    currentPrice: currentPrice == null ? null : Number(currentPrice),
    priceChange1h: priceChange1h == null ? null : Number(priceChange1h),
    volume24h,
    volumeChangePct: volumeChangePct == null ? null : Number(volumeChangePct),
    volumeChangeIsEstimated: Boolean(row.volume_change_is_estimated ?? isEstimated),
    // keep raw for debugging
    _raw: row,
  };
}

export function normalizeTableRow(row: any) {
  // Reuse banner normalizer as table rows are similar; add rank if present
  const base = normalizeBannerRow(row);
  return {
    ...base,
    rank: row.rank ?? row.position ?? null,
    trendDirection: row.trend_direction ?? row.trendDirection ?? null,
    trendScore: row.trend_score ?? row.trendScore ?? null,
    trendStreak: row.trend_streak ?? row.trendStreak ?? null,
  };
}

export default { normalizeBannerRow, normalizeTableRow };
