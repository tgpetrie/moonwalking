import React, { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import { fetchData, API_ENDPOINTS } from '../api.js';
import { motion } from 'framer-motion';

const SentimentIndicator = ({ score }) => {
  const scorePct = ((score + 1) / 2) * 100;
  let colorClass = 'bg-gray-400';
  let label = 'Neutral';

  if (score > 0.6) {
    colorClass = 'bg-green-400';
    label = 'Very Positive';
  } else if (score > 0.2) {
    colorClass = 'bg-green-500';
    label = 'Positive';
  } else if (score < -0.6) {
    colorClass = 'bg-red-600';
    label = 'Very Negative';
  } else if (score < -0.2) {
    colorClass = 'bg-red-500';
    label = 'Negative';
  }

  return (
    <div className="w-full">
      <div className="flex justify-between items-center mb-1 text-xs">
        <span className="font-bold text-gray-300">{label}</span>
        <span className="font-mono text-white">{score.toFixed(2)}</span>
      </div>
      <div className="w-full bg-gray-700 rounded-full h-2">
        <div className={`${colorClass} h-2 rounded-full transition-all duration-500`} style={{ width: `${scorePct}%` }}></div>
      </div>
    </div>
  );
};

SentimentIndicator.propTypes = {
  score: PropTypes.number.isRequired,
};

export default function SentimentPanel({ symbols = [] }) {
  const [sentiment, setSentiment] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!symbols || symbols.length === 0) {
      setSentiment([]);
      setLoading(false);
      return;
    }

    let cancelled = false;
    const fetchSentiment = async () => {
      setLoading(true);
      try {
        const response = await fetchData(API_ENDPOINTS.sentiment(symbols.join(',')));
        if (!cancelled && response.ok) {
          setSentiment(response.sentiment || []);
        }
      } catch (error) {
        console.error("Failed to fetch sentiment data:", error);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    fetchSentiment();
    return () => { cancelled = true; };
  }, [symbols.join(',')]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 20 }}
      transition={{ duration: 0.3 }}
      className="fixed bottom-24 right-6 z-40 w-80 bg-black/80 backdrop-blur-md rounded-xl shadow-lg border border-purple-800/50 p-4"
    >
      <h3 className="text-lg font-headline font-bold text-orange-400 mb-4 text-center">Social Sentiment</h3>
      <div className="space-y-4 max-h-80 overflow-y-auto pr-2">
        {loading ? <div className="text-center text-gray-400 animate-pulse">Loading sentiment...</div>
         : sentiment.length > 0 ? sentiment.map(item => (
            <div key={item.symbol}>
              <h4 className="font-bold text-white mb-1">{item.symbol}</h4>
              <SentimentIndicator score={item.score} />
            </div>
          ))
         : <div className="text-center text-gray-500">No sentiment data for symbols in your watchlist.</div>}
      </div>
    </motion.div>
  );
}

SentimentPanel.propTypes = {
  symbols: PropTypes.arrayOf(PropTypes.string),
};