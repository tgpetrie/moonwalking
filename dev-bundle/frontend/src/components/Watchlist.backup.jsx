import React, { useState, useEffect } from 'react';
import { API_ENDPOINTS, fetchData } from '../api';
import { getWatchlist, addToWatchlist, removeFromWatchlist } from '../api';
import { RiDeleteBinLine } from 'react-icons/ri';

const COIN_LIST = [
  'BTC', 'ETH', 'SOL', 'ADA', 'XRP', 'DOGE', 'LTC', 'AVAX', 'DOT', 'ATOM', 'NEAR', 'PEPE', 'SHIB', 'FLOKI', 'BONK', 'WIF', 'SEI', 'BNB', 'LINK', 'MATIC', 'ARB', 'OP', 'TIA', 'RNDR', 'UNI', 'AAVE', 'SUI', 'JUP', 'PYTH', 'USDT', 'USDC', 'WBTC', 'TRX', 'BCH', 'ETC', 'FIL', 'STX', 'IMX', 'MKR', 'GRT', 'LDO', 'INJ', 'RUNE', 'DYDX', 'CAKE', 'SAND', 'AXS', 'MANA', 'APE', 'GMT', 'ENS', '1INCH', 'COMP', 'CRV', 'SNX', 'YFI', 'ZRX', 'BAT', 'KNC', 'BAL', 'CVX', 'SUSHI', 'UMA', 'BNT', 'REN', 'SRM', 'ALGO', 'CRO', 'FTM', 'KAVA', 'MINA', 'XLM', 'VET', 'HBAR', 'QNT', 'EGLD', 'XTZ', 'CHZ', 'GALA', 'FLOW', 'ENJ', 'ANKR', 'CELO', 'CKB', 'DASH', 'RVN', 'ZIL', 'ICX', 'ONT', 'QTUM', 'SC', 'WAVES', 'XEM', 'ZEN', 'ZEC', 'LSK', 'STEEM', 'BTS', 'ARDR', 'STRAX', 'SYS', 'NXT', 'FCT', 'DCR', 'GAME', 'BLOCK', 'NAV', 'VTC', 'PIVX', 'XVG', 'EXP', 'NXS', 'NEO', 'GAS', 'DGB', 'BTG', 'XMR'
];

const Watchlist = ({ onWatchlistChange, topWatchlist, quickview }) => {
  const [showAll, setShowAll] = useState(false);
  const [search, setSearch] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [searchError, setSearchError] = useState(null);
  const [watchlist, setWatchlist] = useState(topWatchlist || []);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [popStar, setPopStar] = useState(null);
  const [removedBadge, setRemovedBadge] = useState(null);
  const [watchlistData, setWatchlistData] = useState({});

  useEffect(() => {
    const coinList = COIN_LIST;
    if (typeof search !== 'string' || search.trim() === '') {
      setSearchResults([]);
      setSearchError(null);
      return;
    }
    const results = coinList.filter(
      c => typeof c === 'string' && c.toLowerCase().includes(search.trim().toLowerCase()) && !watchlist.includes(c)
    ).slice(0, 8);
    setSearchResults(results);
    setSearchError(results.length === 0 ? 'No coins found or already in watchlist.' : null);
  }, [search, watchlist]);

  const handleAddFromSearch = async (symbol) => {
    try {
      setLoading(true);
      const updated = await addToWatchlist(symbol);
      setWatchlist(updated);
      setSearch('');
      setSearchResults([]);
      setSearchError(null);
      if (onWatchlistChange) onWatchlistChange(updated);
    } catch (err) {
      setSearchError('Failed to add coin.');
    } finally {
      setLoading(false);
    }
  };

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
    if (typeof topWatchlist !== 'undefined') {
      setWatchlist(topWatchlist);
      setLoading(false);
    } else {
      fetchWatchlist();
    }
  }, [topWatchlist]);

  useEffect(() => {
    const fetchAllData = async () => {
      if (!watchlist || watchlist.length === 0) {
        setWatchlistData({});
        return;
      }
      try {
        const requests = watchlist.map(async symbol => {
          try {
            const priceRes = await fetch(`https://api.coinbase.com/v2/prices/${symbol}-USD/spot`);
            const priceJson = await priceRes.json();
            const price = priceJson && priceJson.data && priceJson.data.amount ? parseFloat(priceJson.data.amount) : null;
            return { symbol, price, change: null };
          } catch (err) {
            return { symbol, price: null, change: null };
          }
        });
        const results = await Promise.all(requests);
        const map = {};
        results.forEach(({ symbol, price, change }) => {
          map[symbol] = { price, change };
        });
        setWatchlistData(map);
      } catch (err) {
        setWatchlistData({});
      }
    };
    fetchAllData();
  }, [watchlist]);

  const handleRemove = async (symbol) => {
    try {
      setPopStar(symbol);
      setRemovedBadge(symbol);
      setTimeout(() => setPopStar(null), 350);
      setTimeout(() => setRemovedBadge(null), 1200);
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

  if (loading) return (
    <div className="text-center py-8">
      <div className="animate-pulse text-orange-400 font-mono">Loading Watchlist...</div>
    </div>
  );

  return (
    <div className="flex flex-col space-y-4 w-full max-w-4xl mx-auto h-full min-h-[420px] px-1 sm:px-3 md:px-0 align-stretch">
      {watchlist.length === 0 ? (
        <div className="text-center py-8">
          <div className="text-gray-400 font-mono italic">
            <span role="img" aria-label="star">⭐</span> Track coins by adding them to your watchlist!
          </div>
        </div>
      ) : (
        <React.Fragment>
          <div className="flex flex-col items-center w-full max-w-md mx-auto">
            <input
              type="text"
              className="w-full rounded-lg border border-orange-300 bg-black/40 px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-orange-400 mb-2"
              placeholder="Search to add coin (e.g. BTC, ETH)"
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
            {search && (
              <div className="w-full bg-black/90 border border-orange-300 rounded-lg shadow-lg z-10">
                {searchResults.map(symbol => (
                  <div
                    key={symbol}
                    className="px-4 py-2 hover:bg-orange-400/20 cursor-pointer text-white text-base"
                    onClick={() => handleAddFromSearch(symbol)}
                  >
                    {symbol}
                  </div>
                ))}
                {searchError && <div className="px-4 py-2 text-orange-300 text-sm">{searchError}</div>}
              </div>
            )}
          </div>
          {watchlist.length > 0 && (
            <>
              {(showAll ? watchlist : watchlist.slice(0, 4)).map((symbol, idx) => {
                const data = watchlistData[symbol] || {};
                const price = typeof data.price === 'number' ? (data.price < 1 && data.price > 0 ? `$${data.price.toFixed(4)}` : `$${data.price.toFixed(2)}`) : '--';
                let prevPrice = '--';
                if (typeof data.price === 'number' && typeof data.change === 'number') {
                  const prev = data.price / (1 + data.change / 100);
                  prevPrice = prev < 1 && prev > 0 ? `$${prev.toFixed(4)}` : `$${prev.toFixed(2)}`;
                }
                const change = typeof data.change === 'number' ? `${data.change.toFixed(2)}%` : '--';
                const changeColor = 'text-gray-400';
                return (
                  <div key={symbol} className="relative group">
                    <div
                      className={
                        `flex items-center justify-between p-4 rounded-xl transition-all duration-300 cursor-pointer relative overflow-hidden group-hover:text-orange-400 group-hover:text-shadow-orange-400 ` +
                        `group-hover:scale-[1.035] group-hover:z-10 ` +
                        `will-change-transform` +
                        (popStar === symbol ? ' animate-star-pop' : '')
                      }
                      style={{ boxShadow: '0 2px 16px 0 rgba(255,193,7,0.08)' }}
                    >
                      <span className="font-mono text-lg text-white truncate">{symbol}</span>
                      <span className="ml-4 text-teal-300 font-mono text-base">{price}</span>
                      <span className="ml-4 text-teal-300 font-mono text-base">{prevPrice}</span>
                      <div className="flex flex-col items-center ml-4">
                        <span className={`font-mono text-base ${changeColor}`}>{change}</span>
                        <span className="text-xs text-gray-400">1min</span>
                      </div>
                      <button
                        onClick={() => handleRemove(symbol)}
                        className="text-red-500 hover:text-red-400 transition-colors flex-shrink-0 ml-4"
                      >
                        <RiDeleteBinLine size={20} />
                      </button>
                      {removedBadge === symbol && (
                        <span className="ml-2 px-2 py-0.5 rounded bg-orange-500/80 text-white text-xs font-bold animate-fade-in-out shadow-lg shadow-orange-400/30" style={{animation:'fadeInOut 1.2s'}}>Removed!</span>
                      )}
                    </div>
                    {idx < (showAll ? watchlist.length : Math.min(4, watchlist.length)) - 1 && (
                      <div className="mx-auto my-0.5" style={{height:'2px',width:'60%',background:'linear-gradient(90deg,rgba(254,164,0,0.18) 0%,rgba(254,164,0,0.38) 50%,rgba(254,164,0,0.18) 100%)',borderRadius:'2px'}}></div>
                    )}
                  </div>
                );
              })}
              {watchlist.length > 4 && (
                <div className="flex justify-center mt-2">
                  <button
                    className="px-4 py-2 rounded bg-orange-500 text-white font-bold shadow hover:bg-orange-600 transition-colors"
                    onClick={() => setShowAll(s => !s)}
                  >
                    {showAll ? 'Show Less' : 'Show More'}
                  </button>
                </div>
              )}
            </>
          )}
        </React.Fragment>
      )}
    </div>
  );
};

function WatchlistRow({ symbol, onRemove, removedBadge, popStar }) {
  const [expanded, setExpanded] = useState(false);
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  const fetchCoinData = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetchData(API_ENDPOINTS.gainersTable1Min);
      if (response && response.data && Array.isArray(response.data)) {
        const coin = response.data.find(
          item => (item.symbol?.replace('-USD', '') || item.symbol) === symbol
        );
        if (coin) {
          setData({
            price: coin.current_price,
            change: coin.price_change_percentage_1min
          });
        } else {
          setData(null);
          setError('No data found');
        }
      } else {
        setError('No data');
      }
    } catch (e) {
      setError('Error fetching data');
    } finally {
      setLoading(false);
    }
  };

  const handleExpand = () => {
    if (!expanded) fetchCoinData();
    setExpanded(e => !e);
  };

  return (
    <div className="relative group">
      <div
        className={
          `flex items-center justify-between p-4 rounded-xl transition-all duration-300 cursor-pointer relative overflow-hidden group-hover:text-orange-400 group-hover:text-shadow-orange-400 ` +
          `group-hover:scale-[1.035] group-hover:z-10 ` +
          `will-change-transform` +
          (popStar === symbol ? ' animate-star-pop' : '')
        }
        style={{ boxShadow: '0 2px 16px 0 rgba(255,193,7,0.08)' }}
      >
        <span className="font-mono text-lg text-white truncate">{symbol}</span>
        <button
          onClick={handleExpand}
          className="ml-2 px-2 py-1 rounded bg-blue-900 text-blue-200 hover:bg-blue-700 text-xs font-bold transition-colors"
        >
          {expanded ? 'Hide' : 'More'}
        </button>
        {removedBadge === symbol && (
          <span className="ml-2 px-2 py-0.5 rounded bg-orange-500/80 text-white text-xs font-bold animate-fade-in-out shadow-lg shadow-orange-400/30" style={{animation:'fadeInOut 1.2s'}}>Removed!</span>
        )}
        <button onClick={() => onRemove(symbol)} className="text-red-500 hover:text-red-400 transition-colors flex-shrink-0 ml-4">
          <RiDeleteBinLine size={20} />
        </button>
      </div>
      {expanded && (
        <div className="bg-black/70 rounded-xl mt-2 p-3 text-white text-sm flex flex-col gap-1 border border-blue-900">
          {loading ? (
            <span className="text-blue-300 animate-pulse">Loading...</span>
          ) : error ? (
            <span className="text-red-400">{error}</span>
          ) : data ? (
            <>
              <span>Price: <span className="font-mono">${typeof data.price === 'number' ? (data.price < 1 && data.price > 0 ? data.price.toFixed(4) : data.price.toFixed(2)) : 'N/A'}</span></span>
              <span>1-min Change: <span className={data.change > 0 ? 'text-blue-400' : 'text-pink-400'}>{typeof data.change === 'number' ? `${data.change.toFixed(2)}%` : 'N/A'}</span></span>
            </>
          ) : (
            <span className="text-gray-400">No data</span>
          )}
        </div>
      )}
    </div>
  );
}

export default Watchlist;
