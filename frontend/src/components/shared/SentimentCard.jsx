import PropTypes from 'prop-types';
import React, { forwardRef } from 'react';
import { AnimatePresence, motion } from 'framer-motion';

const SentimentCard = forwardRef(function SentimentCard(
  { open, x, y, symbol, sentiment },
  ref
) {
  const { data, loading, error } = sentiment || {};
  return (
    <AnimatePresence>
      {open && (
        <motion.div
          ref={ref}
          className="bh-popover"
          style={{ top: y, left: x }}
          initial={{ opacity: 0, y: -6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -6 }}
          transition={{ duration: 0.16 }}
        >
          <h4>{symbol} sentiment</h4>
          {error && <p className="text-gray-400 text-sm">Error fetching sentiment.</p>}
          {!error && loading && <p className="text-gray-400 text-sm">Loading…</p>}
          {!loading && !error && data && typeof data === 'object' && (
            <div className="space-y-2 text-sm text-gray-100">
              {Object.prototype.hasOwnProperty.call(data, 'score') && (
                <div className="flex justify-between">
                  <span className="text-gray-400">Score</span>
                  <span className="font-mono">
                    {Number.isFinite(Number(data.score)) ? Number(data.score).toFixed(2) : '—'}
                  </span>
                </div>
              )}
              {Object.prototype.hasOwnProperty.call(data, 'confidence') && (
                <div className="flex justify-between">
                  <span className="text-gray-400">Confidence</span>
                  <span className="font-mono">
                    {Number.isFinite(Number(data.confidence)) ? Number(data.confidence).toFixed(2) : '—'}
                  </span>
                </div>
              )}
              {typeof data.bulls === 'number' && typeof data.bears === 'number' && (
                <div className="flex justify-between">
                  <span className="text-gray-400">Bulls / Bears</span>
                  <span className="font-mono">
                    {Math.round((data.bulls ?? 0) * 100)}% / {Math.round((data.bears ?? 0) * 100)}%
                  </span>
                </div>
              )}
              {Array.isArray(data.signals) && data.signals.length > 0 && (
                <div>
                  <div className="text-gray-400 mb-1">Signals</div>
                  <ul className="list-disc pl-5 text-gray-200 space-y-1">
                    {data.signals.slice(0, 5).map((item, idx) => (
                      <li key={idx} className="text-xs leading-snug">
                        {String(item)}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
          {!loading && !error && !data && (
            <p className="text-gray-400 text-sm">No sentiment data available.</p>
          )}
        </motion.div>
      )}
    </AnimatePresence>
  );
});

SentimentCard.propTypes = {
  open: PropTypes.bool,
  x: PropTypes.number,
  y: PropTypes.number,
  symbol: PropTypes.string,
  sentiment: PropTypes.shape({
    loading: PropTypes.bool,
    data: PropTypes.any,
    error: PropTypes.any,
  }),
};

export default SentimentCard;
