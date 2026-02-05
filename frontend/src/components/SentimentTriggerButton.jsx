import React, { useState } from 'react';
import SentimentPopupAdvanced from './SentimentPopupAdvanced';

/**
 * Sentiment Info Trigger Button
 * Opens the advanced sentiment analysis popup
 */
const SentimentTriggerButton = ({ symbol = 'BTC', className = '' }) => {
  const [isPopupOpen, setIsPopupOpen] = useState(false);

  return (
    <>
      <button
        className={`sentiment-info-btn ${className}`}
        onClick={() => setIsPopupOpen(true)}
        aria-label="View detailed sentiment analysis"
        title="View detailed sentiment analysis"
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="10"/>
          <path d="M12 16v-4M12 8h.01"/>
        </svg>
      </button>

      <SentimentPopupAdvanced
        isOpen={isPopupOpen}
        onClose={() => setIsPopupOpen(false)}
        symbol={symbol}
      />

      <style jsx>{`
        .sentiment-info-btn {
          width: 28px;
          height: 28px;
          display: flex;
          align-items: center;
          justify-content: center;
          background: rgba(174, 75, 245, 0.1);
          border: 1px solid rgba(174, 75, 245, 0.3);
          border-radius: 6px;
          color: #ae4bf5;
          cursor: pointer;
          transition: all 200ms ease;
        }

        .sentiment-info-btn:hover {
          background: rgba(174, 75, 245, 0.2);
          border-color: #ae4bf5;
          transform: translateY(-1px);
        }

        .sentiment-info-btn svg {
          width: 16px;
          height: 16px;
        }
      `}</style>
    </>
  );
};

export default SentimentTriggerButton;
