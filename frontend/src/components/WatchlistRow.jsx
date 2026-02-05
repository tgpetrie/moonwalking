import { useIntelligence } from '../context/IntelligenceContext.jsx';
import { formatPrice } from '../utils/format.js';

/**
 * WatchlistRow - Displays a coin in the watchlist with divergence pulse indicator
 *
 * Divergence Detection Rules:
 * - Bullish Divergence: finbert_score > 0.4 AND fear_greed < 35 (Green Pulse)
 * - Bearish Divergence: finbert_score < -0.4 AND fear_greed > 65 (Red Pulse)
 *
 * Note: This component is a pure presenter. It does NOT trigger any API requests.
 * All fetching is handled by the IntelligenceProvider via batch requests.
 */
export default function WatchlistRow({
    symbol,
    rank,
    currentPrice,
    onRemove,
    onInfo
}) {
    const { reports } = useIntelligence();
    const data = reports[symbol?.toUpperCase()];
    const m = data?.metrics;

    // Divergence detection using deterministic rules
    const isBullishDivergence = m?.divergence === "bullish_divergence";
    const isBearishDivergence = m?.divergence === "bearish_divergence";

    const showPulse = isBullishDivergence || isBearishDivergence;
    const pulseType = isBullishDivergence ? 'bull' : 'bear';
    const divergenceLabel = isBullishDivergence
        ? 'Bullish divergence'
        : isBearishDivergence
            ? 'Bearish divergence'
            : 'Divergence detected';
    const narrativeHint = data?.narrative ? ` • ${data.narrative}` : '';
    const tooltip = showPulse ? `${divergenceLabel}${narrativeHint}` : undefined;

    return (
        <div className="watchlist-row">
            <div className="watchlist-row-content">
                {/* Rank */}
                <div className="watchlist-rank">
                    {rank}
                </div>

                {/* Symbol with divergence pulse */}
                <div className="watchlist-symbol">
                    {symbol}
                    {showPulse && (
                        <div
                            className={`mini-pulse ${pulseType}`}
                            title={tooltip}
                            aria-label={tooltip}
                        >
                            <span className="dot"></span>
                            <span className="ring"></span>
                        </div>
                    )}
                </div>

                {/* Price */}
                <div className="watchlist-price">
                    {formatPrice(currentPrice)}
                </div>

                {/* Metrics preview */}
                <div className="watchlist-metrics">
                    {m ? (
                        <div className="flex gap-2 text-xs">
                            <span title="FinBERT Score">
                                FB: {m.finbert_score.toFixed(2)}
                            </span>
                            <span title="Fear & Greed Index">
                                F&G: {m.fear_greed_index || '—'}
                            </span>
                        </div>
                    ) : (
                        <span className="text-orange-400/40 text-xs">—</span>
                    )}
                </div>

                {/* Actions */}
                <div className="watchlist-actions">
                    {onInfo && (
                        <button
                            onClick={() => onInfo(symbol)}
                            className="watchlist-btn-info"
                            title="View details"
                        >
                            ℹ
                        </button>
                    )}
                    {onRemove && (
                        <button
                            onClick={() => onRemove(symbol)}
                            className="watchlist-btn-remove"
                            title="Remove from watchlist"
                        >
                            ×
                        </button>
                    )}
                </div>
            </div>

            {/* Narrative tooltip (appears on hover if divergence detected) */}
            {showPulse && data?.narrative && (
                <div className="watchlist-narrative">
                    {data.narrative}
                </div>
            )}
        </div>
    );
}
