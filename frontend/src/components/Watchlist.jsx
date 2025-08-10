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
    if (typeof topWatchlist !== 'undefined') {
      setWatchlist(topWatchlist);
      setLoading(false);
    } else {
      setLoading(true);
      async function fetchWatchlist() {
        try {
          const data = await getWatchlist();
          console.log('📋 Fetched watchlist from localStorage:', data.length, 'items');
          
          // Get real prices for all symbols in watchlist
          const symbols = data.map(item => typeof item === 'string' ? item : item.symbol);
          const realPrices = await fetchPricesForSymbols(symbols);
          console.log('💰 Fetched real prices for watchlist:', Object.keys(realPrices).length, 'symbols');
          
          const processedData = data.map((item) => {
            const symbol = typeof item === 'string' ? item : item.symbol;
            const priceAtAdd = typeof item === 'object' ? item.priceAtAdd : 0;
            
            // Get current price from real data or fallback
            let currentPrice = priceAtAdd;
            if (realPrices[symbol]) {
              currentPrice = realPrices[symbol].price;
            } else if (latestData.prices && latestData.prices[symbol]) {
              currentPrice = latestData.prices[symbol].price;
            }
            
            return {
              symbol,
              priceAtAdd: priceAtAdd || currentPrice || 100, // use current price as fallback
              currentPrice: currentPrice || priceAtAdd || 100
            };
          });
          
          setWatchlist(processedData);
          if (onWatchlistChange) onWatchlistChange(data);
          setError(null);
        } catch (error) {
          console.error('Failed to fetch watchlist:', error);
          setError('Failed to fetch watchlist');
          setWatchlist([]);
        }
        setLoading(false);
      }
      fetchWatchlist();
    }
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
      if (onWatchlistChange) onWatchlistChange(data);
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
      if (onWatchlistChange) onWatchlistChange(updated);
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

  if (loading) return <div className="text-center text-gray-400 text-base sm:text-lg md:text-xl">Loading Watchlist...</div>;

  return (
    <div className="flex flex-col space-y-1 w-full h-full min-h-[420px] px-1 sm:px-3 md:px-0 align-stretch transition-all duration-300">
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
        </div>
      </div>
      {error && <div className="text-red-500 mb-4 text-sm sm:text-base">{error}</div>}
      {filteredWatchlist.length > 0 ? (
        <>
          {filteredWatchlist.map((item, idx) => {
            // Safe access with fallback values
            const priceAtAdd = item.priceAtAdd || 0;
            const priceNow = item.currentPrice ?? priceAtAdd;
            const change = priceAtAdd > 0 ? ((priceNow - priceAtAdd) / priceAtAdd) * 100 : 0;
            // Compute micro-trend from last few points
            const h = priceHistory[item.symbol] || [];
            const head = h[h.length - 1]?.p;
            const tail = h[Math.max(0, h.length - 5)]?.p;
            const microTrend = head && tail ? Math.sign(head - tail) : 0; // -1, 0, 1
            return (
              <React.Fragment key={item.symbol}>
                <div className={`crypto-row flex items-center px-2 py-1 rounded-lg mb-1 hover:bg-gray-800 transition`}>
                  <div className="block flex-1">
                    <div
                      className="flex items-center justify-between p-4 rounded-xl transition-all duration-300 cursor-pointer relative overflow-hidden group hover:text-amber-500 hover:scale-[1.035] hover:z-10"
                      style={{
                        boxShadow: 'none', // Remove shadow/border
                        background: 'rgba(10, 10, 18, 0.18)' // Transparent fill
                      }}
                    >
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
                      <div className="flex items-center gap-4">
                        <div className="flex items-center justify-center w-8 h-8 rounded-full bg-orange/40 text-orange font-bold text-sm">★</div>
                        <div className="flex-1 flex items-center gap-3 ml-4 relative">
                          <span className="font-bold text-white text-lg tracking-wide">{item.symbol}</span>
                          {latestAlerts[item.symbol] && (
                            <span
                              title={latestAlerts[item.symbol]}
                              className="ml-1 px-2 py-0.5 rounded-full bg-purple-700/70 text-[10px] font-semibold text-white tracking-wider hover:bg-purple-600 cursor-help"
                            >ALERT</span>
                          )}
                          {/* micro-trend arrow */}
                          {microTrend !== 0 && (
                            <span className={`text-xs font-semibold ${microTrend > 0 ? 'text-green-300' : 'text-red-300'}`} title={microTrend>0?'short-term up':'short-term down'}>
                              {microTrend > 0 ? '↑' : '↓'}
                            </span>
                          )}
                        </div>
                      </div>
                      <div className="flex flex-row flex-wrap items-center gap-2 sm:gap-4 ml-0 sm:ml-4 w-full sm:w-auto">
                        {/* tiny sparkline */}
                        <div className="hidden sm:block">
                          <svg width="80" height="24" viewBox="0 0 80 24" className="opacity-70">
                            {(() => {
                              const pts = (priceHistory[item.symbol]||[]).slice(-20);
                              if (pts.length < 2) return null;
                              const ys = pts.map(x => x.p);
                              const min = Math.min(...ys);
                              const max = Math.max(...ys);
                              const range = max - min || 1;
                              const step = 80 / (pts.length - 1);
                              const d = pts.map((x,i) => `${i===0?'M':'L'} ${i*step} ${24 - ((x.p - min)/range)*24}`).join(' ');
                              const positive = change >= 0;
                              return (
                                <>
                                  <path d={d} fill="none" stroke={positive ? '#7FFFD4' : '#FF7F98'} strokeWidth="2" />
                                </>
                              );
                            })()}
                          </svg>
                        </div>
                        <div className="flex flex-col items-end min-w-[72px] sm:min-w-[100px] ml-2 sm:ml-4">
                          <span className="text-base sm:text-lg md:text-xl font-bold text-teal select-text">
                            ${priceNow.toFixed(priceNow < 1 ? 4 : 2)}
                          </span>
                          <span className="text-xs sm:text-sm md:text-base font-light text-gray-400 select-text">
                            ${priceAtAdd.toFixed(priceAtAdd < 1 ? 4 : 2)}
                          </span>
                        </div>
                        <div className="flex flex-col items-end min-w-[56px] sm:min-w-[60px]">
                          <div className={`flex items-center gap-1 font-bold text-base sm:text-lg md:text-xl ${change > 0 ? 'text-blue' : 'text-pink'}`}> 
                            <span>{change > 0 ? '+' : ''}{change.toFixed(2)}%</span>
                          </div>
                          <span className="text-xs sm:text-sm md:text-base font-light text-gray-400">Total</span>
                        </div>
                        <button
                          onClick={() => handleRemove(item.symbol)}
                          className="text-red-500 hover:text-red-400 transition-colors flex-shrink-0 p-2"
                          aria-label="Remove from watchlist"
                        >
                          <RiDeleteBinLine size={20} />
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
                {idx < filteredWatchlist.length - 1 && (
                  <div
                    className="mx-auto my-0.5"
                    style={{
                      height: '2px',
                      width: '60%',
                      background: 'linear-gradient(90deg,rgba(255,165,0,0.10) 0%,rgba(10,10,18,0.38) 50%,rgba(255,165,0,0.10) 100%)',
                      borderRadius: '2px'
                    }}
                  ></div>
                )}
              </React.Fragment>
            );
          })}
        </>
      ) : (<p className="text-gray-400 text-sm sm:text-base text-center">No cryptocurrencies found.</p>)}
    </div>
  );
};

export default Watchlist;