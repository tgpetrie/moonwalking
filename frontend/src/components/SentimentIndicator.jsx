import React from 'react';
import PropTypes from 'prop-types';

/**
 * Compact sentiment indicator showing bullish/bearish/neutral signals
 * Designed to fit inline with table rows
 */
export default function SentimentIndicator({ score, label, size = 'sm' }) {
  if (score == null || typeof score !== 'number') {
    return <span className="text-xs text-gray-500">—</span>;
  }

  // Map score (0-1) to color and icon
  let bgColor, textColor, icon, displayLabel;

  if (score >= 0.7) {
    bgColor = 'bg-green-500/20';
    textColor = 'text-green-400';
    icon = '↑↑';
    displayLabel = label || 'Bullish';
  } else if (score >= 0.6) {
    bgColor = 'bg-green-500/15';
    textColor = 'text-green-400';
    icon = '↑';
    displayLabel = label || 'Positive';
  } else if (score <= 0.3) {
    bgColor = 'bg-red-500/20';
    textColor = 'text-red-400';
    icon = '↓↓';
    displayLabel = label || 'Bearish';
  } else if (score <= 0.4) {
    bgColor = 'bg-red-500/15';
    textColor = 'text-red-400';
    icon = '↓';
    displayLabel = label || 'Negative';
  } else {
    bgColor = 'bg-gray-500/15';
    textColor = 'text-gray-400';
    icon = '—';
    displayLabel = label || 'Neutral';
  }

  const sizeClasses = size === 'sm'
    ? 'text-xs px-1.5 py-0.5 gap-1'
    : 'text-sm px-2 py-1 gap-1.5';

  return (
    <div
      className={`inline-flex items-center ${sizeClasses} ${bgColor} rounded ${textColor} font-mono whitespace-nowrap`}
      title={`Sentiment Score: ${score.toFixed(2)}`}
    >
      <span className="font-bold">{icon}</span>
      <span className="text-[10px] uppercase tracking-tight">{displayLabel}</span>
    </div>
  );
}

SentimentIndicator.propTypes = {
  score: PropTypes.number,
  label: PropTypes.string,
  size: PropTypes.oneOf(['sm', 'md']),
};
