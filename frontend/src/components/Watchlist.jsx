import React, { useState, useEffect } from 'react';
import { RiDeleteBinLine } from 'react-icons/ri';
import { getWatchlist, addToWatchlist, removeFromWatchlist, fetchLatestAlerts } from '../api.js';
import { useWebSocket } from '../context/websocketcontext.jsx';

const Watchlist = ({ onWatchlistChange, topWatchlist, quickview }) => {
  // All hooks must be called unconditionally
  const [watchlist, setWatchlist] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [newSymbol, setNewSymbol] = useState('');
  const [search, setSearch] = useState('');
  const { latestData, fetchPricesForSymbols } = useWebSocket();
  // Maintain a tiny rolling buffer of last few prices per symbol for sparkline/trend
  const [priceHistory, setPriceHistory] = useState({}); // {SYM: [{t, p}, ...max 20]}
  const [latestAlerts, setLatestAlerts] = useState({});

  // Fetch watchlist on mount and when topWatchlist changes
  useEffect(() => {
    const normalizeAndSet = async () => {
      try {
        setLoading(true);
        // Load from localStorage first
        const data = await getWatchlist();
        console.log('📋 Fetched watchlist from localStorage:', data.length, 'items');
        let symbols = data.map((item) => (typeof item === 'string' ? item : item.symbol));
        // If parent provided additional symbols, merge them in
        if (Array.isArray(topWatchlist) && topWatchlist.length > 0) {
          const extra = topWatchlist.map((it) => (typeof it === 'string' ? it : it.symbol)).filter(Boolean);
          symbols = Array.from(new Set([...symbols, ...extra]));
        }
        const realPrices = await fetchPricesForSymbols(symbols);
        console.log('💰 Fetched real prices for watchlist:', Object.keys(realPrices).length, 'symbols');
        const storedMap = {};
        data.forEach((it) => {
          const sym = typeof it === 'string' ? it : it.symbol;
          const pa = typeof it === 'object' ? it.priceAtAdd : undefined;
          if (sym) storedMap[sym] = pa;
        });
        const processedData = symbols.map((symbol) => {
          const priceAtAdd = storedMap[symbol] ?? 0;
          let currentPrice = priceAtAdd;
          if (realPrices[symbol]) {
            currentPrice = realPrices[symbol].price;
          } else if (latestData.prices && latestData.prices[symbol]) {
            currentPrice = latestData.prices[symbol].price;
          }
          return {
            symbol,
            priceAtAdd: priceAtAdd || currentPrice || 100, // use current price as fallback
            currentPrice: currentPrice || priceAtAdd || 100,
          };
        });
        setWatchlist(processedData);
        if (onWatchlistChange) onWatchlistChange(symbols);
        setError(null);
      } catch (error) {
        console.error('Failed to fetch watchlist:', error);
        setError('Failed to fetch watchlist');
        setWatchlist([]);
      } finally {
        setLoading(false);
      }
    };
    normalizeAndSet();
    // eslint-disable-next-line
  }, [topWatchlist]);

  // Update prices from WebSocket context
  useEffect(() => {
    if (latestData.prices && Object.keys(latestData.prices).length > 0) {
      console.log('🔄 Updating watchlist prices from WebSocket context');
      setWatchlist(prevList => 
        prevList.map(item => ({
          ...item,
          currentPrice: latestData.prices[item.symbol]?.price || item.currentPrice
        }))
      );
      // Update per-symbol history for sparkline/trend (cap 20 points)
      setPriceHistory(prev => {
        const next = { ...prev };
        const now = Date.now();
        for (const [sym, info] of Object.entries(latestData.prices)) {
          const p = info?.price;
          if (typeof p !== 'number') continue;
          const arr = next[sym]?.slice(-19) || [];
          arr.push({ t: now, p });
          next[sym] = arr;
        }
        return next;
      });
    }
  }, [latestData.prices]);

  // Fetch latest alerts for displayed symbols whenever watchlist changes
  useEffect(() => {
    const symbols = watchlist.map(i => i.symbol);
    if (symbols.length === 0) return;
    let cancelled = false;
    (async () => {
      const alerts = await fetchLatestAlerts(symbols);
      if (!cancelled) setLatestAlerts(alerts);
    })();
    const id = setInterval(async () => {
      const alerts = await fetchLatestAlerts(symbols);
      if (!cancelled) setLatestAlerts(alerts);
    }, 20000);
    return () => { cancelled = true; clearInterval(id); };
  }, [watchlist]);

  // Fallback interval to update prices if WebSocket is not providing data
  useEffect(() => {
    const interval = setInterval(async () => {
      if (watchlist.length > 0) {
        const symbols = watchlist.map(item => item.symbol);
        const realPrices = await fetchPricesForSymbols(symbols);
        
        if (Object.keys(realPrices).length > 0) {
          console.log('🔄 Updating watchlist prices via API fallback');
          setWatchlist(prevList => 
            prevList.map(item => ({
              ...item,
              currentPrice: realPrices[item.symbol]?.price || item.currentPrice
            }))
          );
        }
      }
    }, 30000); // Check every 30 seconds
    return () => clearInterval(interval);
  }, [watchlist.length, fetchPricesForSymbols]);

  const handleRemove = async (symbol) => {
    setLoading(true);
    try {
      const data = await removeFromWatchlist(symbol);
      console.log('🗑️ Removed from watchlist:', symbol);
      
      // Get real prices for remaining symbols
      const symbols = data.map(item => typeof item === 'string' ? item : item.symbol);
      const realPrices = await fetchPricesForSymbols(symbols);
      
      // Process the data with real prices
      const processedData = data.map((item) => {
        const itemSymbol = typeof item === 'string' ? item : item.symbol;
        const priceAtAdd = typeof item === 'object' ? item.priceAtAdd : 0;
        
        // Get current price from real data
        let currentPrice = priceAtAdd;
        if (realPrices[itemSymbol]) {
          currentPrice = realPrices[itemSymbol].price;
        } else if (latestData.prices && latestData.prices[itemSymbol]) {
          currentPrice = latestData.prices[itemSymbol].price;
        }
        
        return {
          symbol: itemSymbol,
          priceAtAdd: priceAtAdd || currentPrice || 100,
          currentPrice: currentPrice || priceAtAdd || 100
        };
      });
      
  setWatchlist(processedData);
  // notify parent with symbols only
  if (onWatchlistChange) onWatchlistChange(symbols);
      setError(null);
    } catch (error) {
      console.error(`Failed to remove ${symbol}:`, error);
      setError(`Failed to remove ${symbol}`);
    }
    setLoading(false);
  };

  const handleAdd = async () => {
    const symbol = newSymbol.trim().toUpperCase();
    if (!symbol) return;
    
    try {
      // Get real current price for the symbol
      const realPrices = await fetchPricesForSymbols([symbol]);
      let currentPrice = 100; // fallback price
      
      if (realPrices[symbol]) {
        currentPrice = realPrices[symbol].price;
      } else if (latestData.prices && latestData.prices[symbol]) {
        currentPrice = latestData.prices[symbol].price;
      }
      
      console.log('➕ Adding to watchlist:', symbol, 'at price:', currentPrice);
  const updated = await addToWatchlist(symbol, currentPrice);
      
  // Get real prices for all symbols in updated watchlist
  const symbols = updated.map(item => typeof item === 'string' ? item : item.symbol);
      const allRealPrices = await fetchPricesForSymbols(symbols);
      
      const processedData = updated.map((item) => {
        const itemSymbol = typeof item === 'string' ? item : item.symbol;
        const priceAtAdd = typeof item === 'object' ? item.priceAtAdd : currentPrice;
        
        // Get current price from real data
        let itemCurrentPrice = priceAtAdd;
        if (allRealPrices[itemSymbol]) {
          itemCurrentPrice = allRealPrices[itemSymbol].price;
        } else if (latestData.prices && latestData.prices[itemSymbol]) {
          itemCurrentPrice = latestData.prices[itemSymbol].price;
        }
        
        return {
          symbol: itemSymbol,
          priceAtAdd: priceAtAdd || itemCurrentPrice || 100,
          currentPrice: itemCurrentPrice || priceAtAdd || 100
        };
      });
      
  setWatchlist(processedData);
  // notify parent with symbols only for cross-component includes()
  if (onWatchlistChange) onWatchlistChange(symbols);
      setNewSymbol('');
      setError(null);
    } catch (error) {
      console.error(`Failed to add ${symbol}:`, error);
      setError(`Failed to add ${symbol}`);
    }
  };

  const filteredWatchlist = search
    ? watchlist.filter(item => item.symbol.toLowerCase().includes(search.trim().toLowerCase()))
    : watchlist;

  // Show inputs immediately; display a small inline loading hint instead of blocking UI
  const LoadingHint = loading ? (
    <div className="text-gray-400 text-xs ml-2">Syncing…</div>
  ) : null;

  return (
    <div className="w-full h-full min-h-[420px] px-1 sm:px-3 md:px-0">
      {/* Header now handled by parent app.jsx */}
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
      {LoadingHint}
        </div>
      </div>
      {error && <div className="text-red-500 mb-4 text-sm sm:text-base">{error}</div>}
      {filteredWatchlist.length > 0 ? (
        <>
          {filteredWatchlist.map((r, idx) => {
            // Safe access with fallback values
            const priceAtAdd = r.priceAtAdd || 0;
            const priceNow = r.currentPrice ?? priceAtAdd;
            const change = priceAtAdd > 0 ? ((priceNow - priceAtAdd) / priceAtAdd) * 100 : 0;
            // Compute micro-trend from last few points
            const h = priceHistory[r.symbol] || [];
            const head = h[h.length - 1]?.p;
            const tail = h[Math.max(0, h.length - 5)]?.p;
            const microTrend = head && tail ? Math.sign(head - tail) : 0; // -1, 0, 1
            const url = `https://www.coinbase.com/advanced-trade/spot/${r.symbol.toLowerCase()}-USD`;

            return (
              <div key={r.symbol} className="px-2 py-1 mb-1">
                <a href={url} target="_blank" rel="noopener noreferrer" className="block group">
                  <div className="relative overflow-hidden rounded-xl p-4 hover:scale-[1.02] sm:hover:scale-[1.035] transition-transform">

                    <span className="pointer-events-none absolute inset-0 flex items-center justify-center z-0">
                      <span
                        className="block rounded-2xl transition-all duration-150 opacity-0 group-hover:opacity-100 group-hover:w-[160%] group-hover:h-[160%] w-[120%] h-[120%]"
                        style={{
                          background: 'radial-gradient(circle at 50% 50%, rgba(255,165,0,0.28) 0%, rgba(255,165,0,0.18) 35%, rgba(255,165,0,0.10) 60%, rgba(255,165,0,0.04) 80%, transparent 100%)',
                          top: '-30%',
                          left: '-30%',
                          position: 'absolute',
                          filter: 'blur(1.5px)'
                        }}
                      />
                    </span>

                    <div className="relative z-10 grid grid-cols-[1fr_140px_88px_72px] items-center gap-2 sm:gap-3">

                      {/* LEFT flexible: rank + symbol */}
                      <div className="flex items-center gap-3 sm:gap-4 min-w-0">
                        <div className="flex items-center justify-center w-8 h-8 rounded-full bg-orange/40 text-orange font-bold text-sm shrink-0">★</div>
                        <div className="min-w-0">
                          <div className="font-bold text-white text-lg tracking-wide truncate">{truncateSymbol(r.symbol, 6)}</div>
                        </div>
                      </div>

                      {/* PRICE (140px) */}
                      <div className="flex flex-col items-end w-[140px] tabular-nums whitespace-nowrap">
                        <span className="text-base sm:text-lg md:text-xl font-bold text-teal font-mono">
                          {Number.isFinite(priceNow) ? `${priceNow < 1 && priceNow > 0 ? priceNow.toFixed(4) : priceNow.toFixed(2)}` : 'N/A'}
                        </span>
                        <span className="text-xs sm:text-sm md:text-base font-light text-gray-400 font-mono">
                          {Number.isFinite(priceAtAdd) ? `${priceAtAdd < 1 && priceAtAdd > 0 ? priceAtAdd.toFixed(4) : priceAtAdd.toFixed(2)}` : '--'}
                        </span>
                      </div>

                      {/* % CHANGE (88px) */}
                      <div className="flex flex-col items-end w-[88px] tabular-nums whitespace-nowrap">
                        <div className={`flex items-center gap-1 font-bold text-base sm:text-lg md:text-xl ${change > 0 ? 'text-blue' : 'text-pink'}`}>
                          {change > 0 && <span className="font-mono">+</span>}
                          <span className="font-mono">{typeof change === 'number' ? formatPercentage(change) : 'N/A'}</span>
                        </div>
                      </div>

                      {/* Delete Button (72px) */}
                      <div className="flex items-center justify-end w-[72px]">
                        <button
                          onClick={(e) => {e.preventDefault(); handleRemove(r.symbol);}}
                          className="text-red-500 hover:text-red-400 transition-colors flex-shrink-0 p-2"
                          aria-label="Remove from watchlist"
                        >
                          <RiDeleteBinLine size={20} />
                        </button>
                      </div>
                    </div>

                    <div className="mt-1 relative z-10 flex items-center justify-between min-h-[16px]">
                      <span className="uppercase tracking-wide text-gray-400 text-[10px]">TOTAL</span>
                      <div className="flex items-center gap-2">
                        {/* Sparkline can go here */}
                      </div>
                    </div>

                  </div>
                </a>
              </div>
            );
          })}
        </>
      ) : (<p className="text-gray-400 text-sm sm:text-base text-center">No cryptocurrencies found.</p>)}
    </div>
  );
};

export default Watchlist;