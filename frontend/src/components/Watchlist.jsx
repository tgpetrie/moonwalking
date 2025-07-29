import React, { useState, useEffect } from 'react';
// Local storage helpers for watchlist
const WATCHLIST_KEY = 'crypto_watchlist';

function getCurrentPrices(symbols) {
  // Simulate price fetch (replace with real fetch if needed)
  const prices = {};
  symbols.forEach((symbol) => {
    prices[symbol] = parseFloat((Math.random() * 1000).toFixed(2)); // Simulated price
  });
  return prices;
}

function addToWatchlistLocal(symbol, price) {
  const list = getWatchlistLocal();
  if (!list.some((s) => s.symbol === symbol)) {
    const updated = [...list, { symbol, priceAtAdd: price }];
    window.localStorage.setItem(WATCHLIST_KEY, JSON.stringify(updated));
    return updated;
  }
  return list;
}

function getWatchlistLocal() {
  try {
    const raw = window.localStorage.getItem(WATCHLIST_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function removeFromWatchlistLocal(symbol) {
  const list = getWatchlistLocal();
  const updated = list.filter(s => s.symbol !== symbol);
  window.localStorage.setItem(WATCHLIST_KEY, JSON.stringify(updated));
  return updated;
}
import { RiDeleteBinLine } from 'react-icons/ri';

const Watchlist = ({ onWatchlistChange, topWatchlist, quickview }) => {
  // All hooks must be called unconditionally
  const [watchlist, setWatchlist] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [newSymbol, setNewSymbol] = useState('');
  const [search, setSearch] = useState('');

  // Fetch watchlist on mount and when topWatchlist changes
  useEffect(() => {
    if (typeof topWatchlist !== 'undefined') {
      setWatchlist(topWatchlist);
      setLoading(false);
    } else {
      setLoading(true);
      try {
        const data = getWatchlistLocal();
        setWatchlist(data.map((item) => ({
          ...item,
          currentPrice: item.priceAtAdd,
        })));
        if (onWatchlistChange) onWatchlistChange(data);
        setError(null);
      } catch (error) {
        setError('Failed to fetch watchlist');
        setWatchlist([]);
      }
      setLoading(false);
    }
    // eslint-disable-next-line
  }, [topWatchlist]);

  useEffect(() => {
    const interval = setInterval(() => {
      setWatchlist((prevList) => {
        const symbols = prevList.map(item => item.symbol);
        const newPrices = getCurrentPrices(symbols);
        return prevList.map(item => ({
          ...item,
          currentPrice: newPrices[item.symbol],
        }));
      });
    }, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleRemove = (symbol) => {
    setLoading(true);
    try {
      const data = removeFromWatchlistLocal(symbol);
      setWatchlist(data);
      if (onWatchlistChange) onWatchlistChange(data);
      setError(null);
    } catch (error) {
      setError(`Failed to remove ${symbol}`);
    }
    setLoading(false);
  };

  const handleAdd = () => {
    const symbol = newSymbol.trim().toUpperCase();
    if (!symbol) return;
    const fakePrice = parseFloat((Math.random() * 1000).toFixed(2)); // Replace with real price fetch
    const updated = addToWatchlistLocal(symbol, fakePrice);
    setWatchlist(updated.map((item) => ({
      ...item,
      currentPrice: item.currentPrice || item.priceAtAdd,
    })));
    if (onWatchlistChange) onWatchlistChange(updated);
    setNewSymbol('');
    setError(null);
  };

  const filteredWatchlist = search
    ? watchlist.filter(item => item.symbol.toLowerCase().includes(search.trim().toLowerCase()))
    : watchlist;

  if (loading) return <div className="text-center text-gray-400 text-base sm:text-lg md:text-xl">Loading Watchlist...</div>;

  return (
    <div className="space-y-3 w-full max-w-2xl mx-auto px-1 sm:px-3 md:px-0">
      <h2 className="text-xl sm:text-2xl md:text-3xl font-bold mb-4 text-center" style={{ color: '#FEA400', letterSpacing: '0.01em' }}>MY WATCHLIST</h2>
      {/* Add search input and add symbol input/button */}
      <div className="flex flex-col gap-2 mb-2">
        <input
          type="text"
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search your watchlist..."
          className="px-3 py-2 rounded border border-blue-300 bg-black text-white focus:outline-none focus:ring-2 focus:ring-blue-400 mb-1"
        />
        <div className="flex items-center gap-2">
          <input
            type="text"
            value={newSymbol}
            onChange={e => setNewSymbol(e.target.value)}
            placeholder="Add symbol (e.g. BTC)"
            className="px-3 py-2 rounded border border-orange-300 bg-black text-white focus:outline-none focus:ring-2 focus:ring-orange-400"
          />
          <button
            onClick={handleAdd}
            className="px-4 py-2 rounded bg-orange-500 text-white font-bold shadow hover:bg-orange-600 transition-colors"
          >
            Add
          </button>
        </div>
      </div>
      {error && <div className="text-red-500 mb-4 text-sm sm:text-base">{error}</div>}
      {filteredWatchlist.length > 0 ? (
        <div className="flex flex-col gap-2 items-start">
          {filteredWatchlist.map((item) => {
            const priceNow = item.currentPrice ?? item.priceAtAdd;
            const change = ((priceNow - item.priceAtAdd) / item.priceAtAdd) * 100;
            return (
              <div key={item.symbol} className="flex items-center justify-between w-full p-3 sm:p-4 rounded-xl transition-all duration-300 cursor-pointer relative overflow-hidden bg-transparent border border-orange-200/30 min-w-0">
                <div className="flex flex-col items-start flex-1">
                  <span className="font-mono text-base sm:text-lg md:text-xl text-white truncate">{item.symbol}</span>
                  <span className="text-xs text-gray-400 block">Added: ${item.priceAtAdd.toFixed(2)} | Now: ${priceNow.toFixed(2)} | {change > 0 ? '+' : ''}{change.toFixed(2)}%</span>
                </div>
                <button onClick={() => handleRemove(item.symbol)} className="text-red-500 hover:text-red-400 transition-colors flex-shrink-0">
                  <RiDeleteBinLine size={18} />
                </button>
              </div>
            );
          })}
        </div>
      ) : (<p className="text-gray-400 text-sm sm:text-base text-center">No cryptocurrencies found.</p>)}
    </div>
  );
};

export default Watchlist;