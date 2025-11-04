// Minimal sentiment color helper used by presentational components and tests.
export function colorForSentiment(item) {
  // Accept different shapes used across fixtures: item.change, item.peak_gain,
  // item.price_change_percentage_1min, or explicit sentiment property.
  if (!item) return '';
  const val = (typeof item.change === 'number' ? item.change :
               typeof item.peak_gain === 'number' ? item.peak_gain :
               typeof item.price_change_percentage_1min === 'number' ? item.price_change_percentage_1min :
               (typeof item.sentiment === 'number' ? item.sentiment : null));
  if (typeof val !== 'number') return '';
  // Positive sentiment -> project token 'text-bhabit-blue', negative -> pink-ish
  return val >= 0 ? 'text-bhabit-blue' : 'text-pink';
}

export default { colorForSentiment };
