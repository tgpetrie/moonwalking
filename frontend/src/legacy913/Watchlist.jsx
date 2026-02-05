// Use the full watchlist implementation (kept as a backup file) so the
// watchlist shows user-tracked symbols instead of duplicating gainers/losers.
// The backup implementation lives under components; reference it explicitly.
// Legacy shim — not used in production.
// Kept only as a reference for the September 13, 2024 watchlist behavior.
// Do NOT import this in active UI code. The canonical implementation is
// `../components/Watchlist.jsx`.

export default function LegacyWatchlistPlaceholder() {
	if (process.env.NODE_ENV !== 'production') {
		// eslint-disable-next-line no-console
		console.warn('[legacy913/Watchlist] Deprecated. Use components/Watchlist.jsx instead.');
	}
	return null;
}