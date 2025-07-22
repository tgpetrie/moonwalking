import React, { useState, useEffect } from 'react';
import { getWatchlist, addToWatchlist, removeFromWatchlist } from '../api';
import { RiDeleteBinLine } from 'react-icons/ri';

const Watchlist = ({ onWatchlistChange, topWatchlist, quickview }) => {
  // If topWatchlist is provided, use it as the source of truth
  const [watchlist, setWatchlist] = useState(topWatchlist || []);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchWatchlist = async () => {
    try {
      setLoading(true);
      const data = await getWatchlist();
      setWatchlist(data);
      if (onWatchlistChange) onWatchlistChange(data);
    } catch (error) {
      setError(error.message || 'Failed to fetch watchlist');
      setWatchlist([]);
    } finally {
      setLoading(false);
    }
  };

  // If topWatchlist is provided, always sync local state to it
  useEffect(() => {
    if (typeof topWatchlist !== 'undefined') {
      setWatchlist(topWatchlist);
      setLoading(false);
    } else {
      fetchWatchlist();
    }
    // eslint-disable-next-line
  }, [topWatchlist]);

  const handleRemove = async (symbol) => {
    try {
      setLoading(true);
      const data = await removeFromWatchlist(symbol);
      setWatchlist(data);
      if (onWatchlistChange) onWatchlistChange(data);
    } catch (error) {
      setError(error.message || `Failed to remove ${symbol}`);
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <div className="text-center text-gray-400 text-base sm:text-lg md:text-xl">Loading Watchlist...</div>;

  return (
    <div className="space-y-3 w-full max-w-lg mx-auto px-2 sm:px-4 md:px-0">
      <h2 className="text-xl sm:text-2xl md:text-3xl font-bold mb-4 text-center" style={{ color: '#FEA400', letterSpacing: '0.01em' }}>MY WATCHLIST</h2>
      {error && <div className="text-red-500 mb-4 text-sm sm:text-base">{error}</div>}
      {watchlist.length > 0 ? (
        <div className="flex flex-col gap-2">
          {watchlist.map((symbol) => (
            <div key={symbol} className="flex items-center justify-between p-3 sm:p-4 rounded-xl transition-all duration-300 cursor-pointer relative overflow-hidden bg-transparent border border-orange-200/30 hover:shadow-lg min-w-0">
              <span className="font-mono text-base sm:text-lg md:text-xl text-white truncate">{symbol}</span>
              <button onClick={() => handleRemove(symbol)} className="text-red-500 hover:text-red-400 transition-colors flex-shrink-0">
                <RiDeleteBinLine size={18} />
              </button>
            </div>
          ))}
        </div>
      ) : (<p className="text-gray-400 text-sm sm:text-base text-center">Add cryptocurrencies to your watchlist.</p>)}
    </div>
  );
};

export default Watchlist;