// Blue = good/buy-ish, Grey = neutral/no signal, Pink = bad/avoid-ish
export function inferSentiment(row) {
  if (!row || typeof row !== 'object') return 'neutral';
  const c1 = Number(row.price_change_percentage_1min);
  const c3 = Number(row.price_change_percentage_3min);
  const delta = Number.isFinite(c1) ? c1 : (Number.isFinite(c3) ? c3 : null);
  if (delta == null) return 'neutral';
  if (delta > 0.5) return 'positive';
  if (delta < -0.5) return 'negative';
  return 'neutral';
}

export function colorForSentiment(rowOrLabel) {
  const s = typeof rowOrLabel === 'string' ? rowOrLabel : inferSentiment(rowOrLabel);
  switch (s) {
    case 'positive': return 'text-bhabit-blue';
    case 'negative': return 'text-bhabit-pink';
    default:         return 'text-zinc-400';
  }
}
