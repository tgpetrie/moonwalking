import React, { useState, useEffect } from 'react';
import { getWatchlist, addToWatchlist, removeFromWatchlist } from '../api';
import { RiDeleteBinLine } from 'react-icons/ri';

const Watchlist = ({ onWatchlistChange }) => {
  const [watchlist, setWatchlist] = useState([]);
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

  useEffect(() => {
    fetchWatchlist();
  }, []);

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

  if (loading) return <div className="text-center text-gray-400">Loading Watchlist...</div>;

  return (
    <div className="w-full max-w-md p-4 bg-gray-800/50 backdrop-blur-sm rounded-xl shadow-lg">
      <h2 className="text-2xl font-bold text-white mb-4">My Watchlist</h2>
      {error && <div className="text-red-500 mb-4">{error}</div>}
      {watchlist.length > 0 ? (
        <ul className="space-y-2">
          {watchlist.map((symbol) => (
            <li key={symbol} className="flex justify-between items-center p-3 bg-gray-700/50 rounded-md">
              <span className="font-mono text-lg text-white">{symbol}</span>
              <button onClick={() => handleRemove(symbol)} className="text-red-500 hover:text-red-400 transition-colors">
                <RiDeleteBinLine size={20} />
              </button>
            </li>
          ))}
        </ul>
      ) : (<p className="text-gray-400">Add cryptocurrencies to your watchlist.</p>)}
    </div>
  );
};

export default Watchlist;