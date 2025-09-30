import React, { useState, useEffect, useMemo } from 'react';
import PropTypes from 'prop-types';
import { useWatchlistContext } from '../hooks/useWatchlist.jsx';
import { formatPrice, formatPercentage } from '../utils/formatters.js';
import { useWebSocket } from '../context/websocketcontext.jsx';
import { fetchData, API_ENDPOINTS } from '../api.js';
import { RiDeleteBinLine } from 'react-icons/ri';
import { FiSearch, FiInfo } from 'react-icons/fi';

const Watchlist = ({ quickview, onSelectCoin }) => {
  const { list: watchlist, loading, toggle } = useWatchlistContext();
  const { latestData } = useWebSocket();

  const [showAll, setShowAll] = useState(false);
  const [search, setSearch] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [searchError, setSearchError] = useState(null);
  const [popStar, setPopStar] = useState(null);
  const [removedBadge, setRemovedBadge] = useState(null);
  const [watchlistData, setWatchlistData] = useState({});
  const [allSymbols, setAllSymbols] = useState([]);

  useEffect(() => {
    const fetchAllSymbols = async () => {
      try {
        const response = await fetchData(API_ENDPOINTS.products);
        // Accept either { products: [...] } or a plain array for resilience
        const list = Array.isArray(response)
          ? response
          : (Array.isArray(response?.products) ? response.products : []);
        if (list.length) {
          setAllSymbols(list.map(s => String(s).toUpperCase()));
        } else {
          setAllSymbols([]);
        }
      } catch (error) {
        console.error("Failed to fetch product list for search", error);
      }
    };
    fetchAllSymbols();
  }, []);

  useEffect(() => {
    const term = search.trim().toLowerCase();
    if (!term) {
      setSearchResults([]);
      setSearchError(null);
      return;
    }
    const results = allSymbols
      .filter(c => c.toLowerCase().includes(term) && !watchlist.includes(c))
      .slice(0, 8);
    setSearchResults(results);
    setSearchError(results.length === 0 ? 'No coins found or already in watchlist.' : null);
  }, [search, watchlist, allSymbols]);

  const handleAddFromSearch = (symbol) => {
    toggle(symbol);
    setSearch('');
    setSearchResults([]);
  };

  const handleRemove = (symbol) => {
    setPopStar(symbol);
    setRemovedBadge(symbol);
    setTimeout(() => setPopStar(null), 350);
    setTimeout(() => setRemovedBadge(null), 1200);
    toggle(symbol);
  };

  // Keep watchlistData updated from WebSocket cache first
  const { fetchPricesForSymbols } = useWebSocket();
  useEffect(() => {
    if (!watchlist.length) {
      setWatchlistData({});
      return;
    }
    const map = {};
    // Build a normalized map of crypto array for faster lookups (normalizedSymbol -> coin)
    const cryptoMap = (Array.isArray(latestData?.crypto) ? latestData.crypto : []).reduce((acc, coin) => {
      const raw = String(coin.symbol || '').toUpperCase();
      const norm = raw.replace(/-USD$/, '');
      acc[norm] = coin;
      acc[raw] = coin;
      return acc;
    }, {});

    watchlist.forEach((s) => {
      const symRaw = String(s || '').toUpperCase();
      const symNorm = symRaw.replace(/-USD$/, '');

      // 1) Try prices map with symbol as stored
      const tryKeys = [symRaw, `${symRaw}-USD`, symNorm, `${symNorm}-USD`];
      let found = false;
      for (const k of tryKeys) {
        if (latestData?.prices && latestData.prices[k]) {
          const p = latestData.prices[k];
          map[symNorm] = { price: p.price, change: p.changePercent ?? p.change ?? null };
          found = true;
          break;
        }
      }

      // 2) Try crypto array normalized map
      if (!found && cryptoMap[symNorm]) {
        const hit = cryptoMap[symNorm];
        map[symNorm] = { price: hit.current_price ?? hit.price ?? null, change: hit.price_change_percentage_1min ?? hit.change ?? null };
        found = true;
      }

      // 3) As a final attempt, try raw symbol in cryptoMap
      if (!found && cryptoMap[symRaw]) {
        const hit = cryptoMap[symRaw];
        map[symNorm] = { price: hit.current_price ?? hit.price ?? null, change: hit.price_change_percentage_1min ?? hit.change ?? null };
      }
    });

    // Merge immediate results
    setWatchlistData((prev) => ({ ...prev, ...map }));

    // Find any symbols still missing and try cached price fetcher for them (tries latestData.crypto/prices)
    (async () => {
      try {
        const missing = watchlist.filter(s => {
          const symRaw = String(s || '').toUpperCase();
          const symNorm = symRaw.replace(/-USD$/, '');
          return !(map[symNorm] || map[symRaw]);
        });
        if (missing.length === 0) return;

        // Build candidate keys to try for each missing symbol
        const candidates = [];
        missing.forEach(s => {
          const symRaw = String(s || '').toUpperCase();
          const symNorm = symRaw.replace(/-USD$/, '');
          candidates.push(symRaw, `${symRaw}-USD`, symNorm, `${symNorm}-USD`);
        });

        const prices = await fetchPricesForSymbols(candidates);
        if (prices && Object.keys(prices).length) {
          const extra = {};
          missing.forEach(s => {
            const symRaw = String(s || '').toUpperCase();
            const symNorm = symRaw.replace(/-USD$/, '');
            // Try candidate keys in order to pick the first returned one
            const tryKeys = [symRaw, `${symRaw}-USD`, symNorm, `${symNorm}-USD`];
            for (const k of tryKeys) {
              if (prices[k]) {
                const p = prices[k];
                extra[symNorm] = { price: p.price, change: p.changePercent ?? p.change ?? null };
                break;
              }
            }
          });
          if (Object.keys(extra).length) {
            setWatchlistData((prev) => ({ ...prev, ...extra }));
          }
        }
      } catch (err) {
        console.error('Watchlist: fetchPricesForSymbols failed', err);
      }
    })();
  }, [latestData, watchlist, fetchPricesForSymbols]);

  if (loading && watchlist.length === 0) {
    return (
      <div className="text-center py-8">
        <div className="animate-pulse text-orange-400 font-mono">Loading Watchlist...</div>
      </div>
    );
  }

  return (
    <div className="flex flex-col space-y-4 w-full h-full min-h-[420px] px-0 align-stretch">
      <div className="flex flex-col w-full">
        <div className="relative">
          <FiSearch className="absolute left-3 top-1/2 -translate-y-1/2 text-purple-300 opacity-70" size={18} />
          <input
            type="text"
            className="w-full rounded-lg border border-purple-800/70 bg-black/40 pl-10 pr-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-purple-500/70 placeholder-gray-400"
            placeholder="Search & add coin (e.g. BTC, ETH)"
            value={search}
            onChange={e => setSearch(e.target.value)}
            aria-label="Search and add coin to watchlist"
          />
        </div>
        <div className="h-0.5 bg-gradient-to-r from-orange-400 via-purple-600 to-orange-400 mt-2 opacity-60"></div>
        {search && (
          <div className="w-full bg-black/90 border border-purple-900 rounded-lg shadow-lg z-10 mt-2">
            {searchResults.map(symbol => (
              <div
                key={symbol}
                className="px-4 py-2 hover:bg-purple-900/30 cursor-pointer text-white text-base flex items-center justify-between"
                onClick={() => handleAddFromSearch(symbol)}
              >
                <span>{symbol}</span>
              </div>
            ))}
            {searchError && <div className="px-4 py-2 text-orange-300 text-sm">{searchError}</div>}
          </div>
        )}
      </div>

      {watchlist.length === 0 ? (
        <div className="text-center py-8">
          <div className="text-gray-400 font-mono italic">
            <span role="img" aria-label="star">⭐</span> Track coins by adding them to your watchlist!
          </div>
        </div>
      ) : (
        <>
          {(showAll ? watchlist : watchlist.slice(0, 4)).map((symbol) => {
            const symRaw = String(symbol || '').toUpperCase();
            const symNorm = symRaw.replace(/-USD$/, '');
            const data = watchlistData[symNorm] || watchlistData[symRaw] || {};
            const pNow = typeof data.price === 'number' ? data.price : null;
            const price = pNow != null ? formatPrice(pNow) : '--';
            const pct = data.change;
            const change = pct != null ? `${pct > 0 ? '+' : ''}${formatPercentage(pct, { decimals: 2, fraction: false })}` : '--';
            const changeColor = pct == null ? 'text-gray-400' : (pct >= 0 ? 'text-pos' : 'text-neg');
            return (
              <div key={symbol} className="relative group">
                <div
                  className={`relative overflow-hidden rounded-xl p-4 h-[96px] transition-transform will-change-transform cursor-pointer group-hover:scale-[1.02] group-hover:z-10 ${popStar === symbol ? ' animate-star-pop' : ''}`}
                  onClick={() => onSelectCoin && onSelectCoin(symbol)}
                  role="button"
                  tabIndex={0}
                >
                  <span aria-hidden className="pointer-events-none absolute left-0 right-0 bottom-0 h-2 z-0">
                    <span className="block w-full h-full" style={{ background: 'radial-gradient(ellipse at 50% 140%, rgba(192,38,211,0.18) 0%, rgba(192,38,211,0.10) 35%, rgba(192,38,211,0.04) 60%, transparent 85%)' }} />
                  </span>
                  <div className="relative z-10 grid grid-cols-[minmax(0,1fr)_152px_108px_28px] gap-x-4 items-start">
                    <div className="min-w-0 flex items-center gap-2">
                      <div className="font-bold text-white text-lg tracking-wide truncate">{symbol}</div>
                      <div className="opacity-0 group-hover:opacity-100 transition-opacity">
                        <FiInfo size={14} className="text-purple-300" title="View Insights" />
                      </div>
                      {removedBadge === symbol && (
                        <span className="px-2 py-0.5 rounded bg-blue/80 text-white text-xs font-bold animate-fade-in-out shadow-blue-400/30">Removed!</span>
                      )}
                    </div>
                    <div className="w-[152px] pr-6 text-right">
                      <div className="text-base sm:text-lg md:text-xl font-bold text-teal font-mono tabular-nums leading-none whitespace-nowrap">
                        {price}
                      </div>
                    </div>
                    <div className="w-[108px] pr-1.5 text-right align-top">
                      <div className={`text-lg sm:text-xl md:text-2xl font-bold tabular-nums leading-none whitespace-nowrap ${changeColor}`}>
                        {change}
                      </div>
                      <div className="text-xs text-gray-400 leading-tight">1m</div>
                    </div>
                    <div className="w-[28px] text-right">
                      <button
                        onClick={(e) => { e.stopPropagation(); handleRemove(symbol); }}
                        className="text-red-500 hover:text-red-400 transition-colors inline-flex items-center justify-end"
                        aria-label="Remove from watchlist"
                      >
                        <RiDeleteBinLine size={20} />
                      </button>
                    </div>
                  </div>
                </div>
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
    </div>
  );
};

Watchlist.propTypes = {
  quickview: PropTypes.bool,
  onSelectCoin: PropTypes.func,
};

export default Watchlist;
