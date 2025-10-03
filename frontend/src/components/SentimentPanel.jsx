import React, { useState, useEffect, useMemo } from 'react';
import PropTypes from 'prop-types';
import { fetchData, API_ENDPOINTS } from '../api.js';
import { motion } from 'framer-motion';

const SentimentBar = ({ score }) => {
  // Score is 0-1 range
  const scorePct = (score * 100);
  let colorClass = 'bg-gray-400';
  let label = 'Neutral';

  if (score >= 0.7) {
    colorClass = 'bg-green-400';
    label = 'Very Bullish';
  } else if (score >= 0.6) {
    colorClass = 'bg-green-500';
    label = 'Bullish';
  } else if (score <= 0.3) {
    colorClass = 'bg-red-600';
    label = 'Very Bearish';
  } else if (score <= 0.4) {
    colorClass = 'bg-red-500';
    label = 'Bearish';
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

SentimentBar.propTypes = {
  score: PropTypes.number.isRequired,
};

export default function SentimentPanel({ symbols = [] }) {
  const [sentiment, setSentiment] = useState([]);
  const [loading, setLoading] = useState(true);
  const symbolKey = useMemo(() => (symbols || []).join(','), [symbols]);

  // Calculate aggregate metrics
  const aggregateMetrics = useMemo(() => {
    if (!sentiment || sentiment.length === 0) return null;

    const avgScore = sentiment.reduce((sum, s) => sum + (s.score || 0.5), 0) / sentiment.length;
    const bullishCount = sentiment.filter(s => s.score >= 0.6).length;
    const bearishCount = sentiment.filter(s => s.score <= 0.4).length;
    const neutralCount = sentiment.length - bullishCount - bearishCount;
    const totalTwitter = sentiment.reduce((sum, s) => sum + (s.twitter_mentions || 0), 0);
    const totalReddit = sentiment.reduce((sum, s) => sum + (s.reddit_posts || 0), 0);
    const avgFearGreed = sentiment.reduce((sum, s) => sum + (s.fear_greed || 50), 0) / sentiment.length;

    return {
      avgScore,
      bullishCount,
      bearishCount,
      neutralCount,
      totalTwitter,
      totalReddit,
      avgFearGreed,
    };
  }, [sentiment]);

  useEffect(() => {
    if (!symbolKey) {
      setSentiment([]);
      setLoading(false);
      return;
    }

    let cancelled = false;
    const fetchSentiment = async () => {
      setLoading(true);
      try {
        const response = await fetchData(API_ENDPOINTS.sentiment(symbolKey));
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
  }, [symbolKey]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 20 }}
      transition={{ duration: 0.3 }}
      className="fixed bottom-24 right-6 z-40 w-96 bg-black/90 backdrop-blur-md rounded-xl shadow-lg border border-purple-800/50 p-5"
    >
      <h3 className="text-lg font-headline font-bold text-orange-400 mb-4 text-center">Sentiment Dashboard</h3>

      {loading ? (
        <div className="text-center text-gray-400 animate-pulse py-8">Loading sentiment...</div>
      ) : sentiment.length > 0 ? (
        <>
          {/* Aggregate Overview */}
          {aggregateMetrics && (
            <div className="mb-5 p-3 bg-white/5 rounded-lg border border-purple-700/30">
              <div className="text-xs font-bold text-gray-400 mb-2 uppercase tracking-wide">Market Overview</div>
              <div className="grid grid-cols-3 gap-3 text-center mb-3">
                <div>
                  <div className="text-lg font-bold text-green-400">{aggregateMetrics.bullishCount}</div>
                  <div className="text-xs text-gray-400">Bullish</div>
                </div>
                <div>
                  <div className="text-lg font-bold text-gray-400">{aggregateMetrics.neutralCount}</div>
                  <div className="text-xs text-gray-400">Neutral</div>
                </div>
                <div>
                  <div className="text-lg font-bold text-red-400">{aggregateMetrics.bearishCount}</div>
                  <div className="text-xs text-gray-400">Bearish</div>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="bg-black/40 p-2 rounded">
                  <div className="text-gray-400">Social Volume</div>
                  <div className="font-mono text-white">{(aggregateMetrics.totalTwitter + aggregateMetrics.totalReddit).toLocaleString()}</div>
                </div>
                <div className="bg-black/40 p-2 rounded">
                  <div className="text-gray-400">Fear & Greed</div>
                  <div className="font-mono text-white">{Math.round(aggregateMetrics.avgFearGreed)}</div>
                </div>
              </div>
            </div>
          )}

          {/* Individual Sentiment Scores */}
          <div className="space-y-3 max-h-80 overflow-y-auto pr-2">
            {sentiment.map(item => (
              <div key={item.symbol} className="p-3 bg-white/5 rounded-lg hover:bg-white/10 transition-colors">
                <div className="flex justify-between items-center mb-2">
                  <h4 className="font-bold text-white">{item.symbol}</h4>
                  <span className="text-xs font-mono text-gray-400">{item.label || 'Neutral'}</span>
                </div>
                <SentimentBar score={item.score} />
                <div className="mt-2 flex gap-2 text-xs">
                  <span className="text-gray-400">
                    <span className="text-blue-400">𝕏</span> {(item.twitter_mentions || 0).toLocaleString()}
                  </span>
                  <span className="text-gray-400">
                    <span className="text-orange-400">⬆</span> {(item.reddit_posts || 0).toLocaleString()}
                  </span>
                  {item.fear_greed && (
                    <span className="text-gray-400 ml-auto">
                      F&G: <span className="text-white font-mono">{item.fear_greed}</span>
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </>
      ) : (
        <div className="text-center text-gray-500 py-8">No sentiment data for watchlist symbols.</div>
      )}
    </motion.div>
  );
}

SentimentPanel.propTypes = {
  symbols: PropTypes.arrayOf(PropTypes.string),
};
