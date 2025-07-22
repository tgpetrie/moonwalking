import React, { useState, useEffect } from 'react';
import StarIcon from './StarIcon';
import { getWatchlist, addToWatchlist, removeFromWatchlist, API_ENDPOINTS, fetchData } from '../api';
import { formatPrice } from '../utils/formatters';
import { RiDeleteBinLine } from 'react-icons/ri';

const Watchlist = ({ onWatchlistChange }) => {
  const [watchlist, setWatchlist] = useState([]);
  const [loading, setLoading] = useState(true);
  const [addSymbol, setAddSymbol] = useState('');
  const [addError, setAddError] = useState('');
  const [adding, setAdding] = useState(false);
  const [prices, setPrices] = useState({});
  const [priceLoading, setPriceLoading] = useState(false);
  // Fetch live prices for all symbols in watchlist
  const fetchPrices = async (symbols) => {
    if (!symbols || symbols.length === 0) {
      setPrices({});
      return;
    }
    setPriceLoading(true);
    try {
      // Backend expects comma-separated symbols, e.g. BTC,ETH
      const query = symbols.join(',');
      const url = `${API_ENDPOINTS.crypto}?symbols=${encodeURIComponent(query)}`;
      const response = await fetchData(url);
      // Response should be an array of objects with symbol and current_price
      const priceMap = {};
      if (Array.isArray(response.data)) {
        response.data.forEach(item => {
          priceMap[item.symbol?.replace('-USD', '')] = item.current_price;
        });
      }
      setPrices(priceMap);
    } catch (err) {
      setPrices({});
    } finally {
      setPriceLoading(false);
    }
  };
  const handleAdd = async (e) => {
    e.preventDefault();
    setAddError('');
    const symbol = addSymbol.trim().toUpperCase();
    if (!symbol) {
      setAddError('Please enter a symbol.');
      return;
    }
    if (watchlist.includes(symbol)) {
      setAddError('Symbol already in watchlist.');
      return;
    }
    setAdding(true);
    try {
      const { data } = await addToWatchlist(symbol);
      setWatchlist(data.watchlist || data);
      onWatchlistChange(data.watchlist || data);
      setAddSymbol('');
    } catch (error) {
      setAddError('Failed to add symbol.');
    } finally {
      setAdding(false);
    }
  };

  const fetchWatchlist = async () => {
    try {
      setLoading(true);
      const { data } = await getWatchlist();
      setWatchlist(data);
      onWatchlistChange(data);
    } catch (error) {
      console.error("Failed to fetch watchlist:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchWatchlist();
  }, []);

  // Fetch prices whenever watchlist changes
  useEffect(() => {
    fetchPrices(watchlist);
    const interval = setInterval(() => fetchPrices(watchlist), 30000);
    return () => clearInterval(interval);
  }, [watchlist]);

  const handleRemove = async (symbol) => {
    try {
      const { data } = await removeFromWatchlist(symbol);
      setWatchlist(data.watchlist);
      onWatchlistChange(data.watchlist);
    } catch (error) {
      console.error(`Failed to remove ${symbol}:`, error);
    }
  };

  if (loading) return <div className="text-center text-gray-400">Loading Watchlist...</div>;

  return (
    <div className="space-y-3">
      {/* Header styled like other tables, but orange */}
      <div className="flex flex-col items-start mb-4" style={{ minHeight: '2.2rem' }}>
        <h2
          className="text-lg font-bold tracking-wide uppercase"
          style={{ color: '#FEA400', lineHeight: '2.2rem', letterSpacing: '0.05em' }}
        >
          MY WATCHLIST
        </h2>
      </div>
      {/* Add symbol form */}
      <form onSubmit={handleAdd} className="flex mb-4 gap-2">
        <input
          type="text"
          className="flex-1 rounded-md px-3 py-2 bg-gray-700 text-white placeholder-gray-400 focus:outline-none"
          placeholder="Add symbol (e.g. BTC)"
          value={addSymbol}
          onChange={e => setAddSymbol(e.target.value)}
          disabled={adding}
        />
        <button
          type="submit"
          className="bg-purple-600 hover:bg-purple-500 text-white px-4 py-2 rounded-md font-bold disabled:opacity-50"
          disabled={adding}
        >
          {adding ? 'Adding...' : 'Add'}
        </button>
      </form>
      {addError && <div className="text-red-400 mb-2">{addError}</div>}
      {/* Watchlist items styled as cards like other tables */}
      {watchlist.length > 0 ? (
        watchlist.map((symbol, idx) => {
          const isInWatchlist = true; // Always true for watchlist
          return (
            <React.Fragment key={symbol}>
              <div className="flex items-center">
                <div className="block group flex-1">
                  <div className="flex items-center justify-between p-4 rounded-xl transition-all duration-300 cursor-pointer relative overflow-hidden group">
                    {/* Diamond inner glow effect (hover only) */}
                    <span className="pointer-events-none absolute inset-0 flex items-center justify-center z-0">
                      <span
                        className="block w-[140%] h-[140%] rounded-xl opacity-0 group-hover:opacity-90 transition-opacity duration-1500"
                        style={{
                          background:
                            'radial-gradient(circle at 50% 50%, rgba(254,164,0,0.16) 0%, rgba(254,164,0,0.08) 60%, transparent 100%)',
                          top: '-20%',
                          left: '-20%',
                          position: 'absolute',
                        }}
                      />
                    </span>
                    <div className="flex items-center gap-4 flex-1">
                      {/* Symbol */}
                      <div className="flex-1 flex items-center gap-3 ml-4">
                        <span className="font-bold text-white text-lg tracking-wide group-hover:text-orange-400 group-hover:text-shadow-orange">
                          {symbol}
                        </span>
                      </div>
                      {/* Price Column (teal, right-aligned) */}
                      <div className="flex flex-col items-end min-w-[100px] ml-4">
                        <span className="text-lg font-bold text-teal">
                          {priceLoading ? '...' : (prices[symbol] !== undefined ? formatPrice(prices[symbol]) : 'N/A')}
                        </span>
                        <span className="text-sm font-light text-gray-400">
                          live price
                        </span>
                      </div>
                      {/* StarIcon on the right, smaller, orange/gold on hover and filled */}
                      <StarIcon
                        filled={isInWatchlist}
                        onClick={() => handleRemove(symbol)}
                        className={`ml-4 w-5 h-5 transition-transform duration-200 ${isInWatchlist ? 'text-[#FEA400] fill-[#FEA400]' : 'text-gray-400'} group-hover:text-[#FEA400] group-hover:fill-[#FEA400] hover:scale-110`}
                        style={{ minWidth: '20px', minHeight: '20px', cursor: 'pointer' }}
                      />
                    </div>
                  </div>
                </div>
              </div>
              {/* Orange divider, not full width, only between cards */}
              {idx < watchlist.length - 1 && (
                <div className="mx-auto my-0.5" style={{height:'2px',width:'60%',background:'linear-gradient(90deg,rgba(254,164,0,0.18) 0%,rgba(254,164,0,0.38) 50%,rgba(254,164,0,0.18) 100%)',borderRadius:'2px'}}></div>
              )}
            </React.Fragment>
          );
        })
      ) : (
        <p className="text-gray-400">Add cryptocurrencies to your watchlist.</p>
      )}
    </div>
  );
};

export default Watchlist;
