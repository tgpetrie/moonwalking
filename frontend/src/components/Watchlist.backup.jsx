import React, { useState, useEffect } from 'react';
import { getWatchlist, addToWatchlist, removeFromWatchlist } from '../api';
import { formatPrice } from '../utils/formatters.js';
import { normalizeTableRow } from '../lib/adapters';
import { useWebSocket } from '../context/websocketcontext.jsx';
import { RiDeleteBinLine } from 'react-icons/ri';
import { FiSearch } from 'react-icons/fi';

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
  const { latestData, isConnected, isPolling } = useWebSocket();

  // Helper: get symbols and lookup maps
  const symbols = Array.isArray(watchlist)
    ? watchlist.map((it) => (typeof it === 'string' ? it : it.symbol)).filter(Boolean)
    : [];
  const priceAtAddMap = (() => {
    const map = {};
    if (Array.isArray(watchlist)) {
      watchlist.forEach((it) => {
        if (typeof it === 'object' && it?.symbol) map[it.symbol] = Number(it.priceAtAdd) || 0;
      });
    }
    return map;
  })();

  const [allSymbols, setAllSymbols] = useState(COIN_LIST);
  const [catalogLoaded, setCatalogLoaded] = useState(false);
  const [catalogUpdatedAt, setCatalogUpdatedAt] = useState(0);
  const CATALOG_KEY = 'watchlist:catalog:v1';

  // Load persisted catalog once (merge with defaults)
  useEffect(() => {
    try {
      const raw = localStorage.getItem(CATALOG_KEY);
      if (raw) {
        const saved = JSON.parse(raw);
        if (saved && Array.isArray(saved.symbols)) {
          const set = new Set(COIN_LIST);
          saved.symbols.forEach(s => { if (typeof s === 'string') set.add(s.toUpperCase()); });
          setAllSymbols(Array.from(set));
          setCatalogLoaded(true);
          setCatalogUpdatedAt(Number(saved.updatedAt) || 0);
        }
      }
    } catch (_) { /* ignore */ }
  }, []);
  useEffect(() => {
    const term = (typeof search === 'string' ? search.trim() : '').toLowerCase();
    if (!term) { setSearchResults([]); setSearchError(null); return; }
    const inSet = new Set(symbols);

    const ensureCatalog = async () => {
      const MIN_REFRESH_MS = 24 * 60 * 60 * 1000; // 24h
      const now = Date.now();
      if (catalogLoaded && (now - (catalogUpdatedAt || 0) < MIN_REFRESH_MS)) return;
      try {
        let merged = null;
        // Prefer Coinbase public v2 currencies (CORS-friendly)
        try {
          const cRes = await fetch('https://api.coinbase.com/v2/currencies');
          const cJson = await cRes.json();
          if (cJson && Array.isArray(cJson.data)) {
            const set = new Set(allSymbols);
            cJson.data.forEach((c) => {
              const isCrypto = c?.details?.type ? String(c.details.type).toLowerCase() === 'crypto' : true;
              if (isCrypto && c?.code) set.add(String(c.code).toUpperCase());
            });
            merged = Array.from(set);
          }
        } catch (_) { /* ignore */ }

        // Fallback to Exchange products if needed
        if (!merged) {
          const res = await fetch('https://api.exchange.coinbase.com/products');
          const products = await res.json();
          if (Array.isArray(products)) {
            const set = new Set(allSymbols);
            products.forEach(p => {
              if (p && typeof p.id === 'string' && p.id.endsWith('-USD')) {
                const sym = p.id.split('-')[0].toUpperCase();
                if (sym) set.add(sym);
              }
            });
            merged = Array.from(set);
          }
        }

        if (merged) {
          setAllSymbols(merged);
          try {
            localStorage.setItem(CATALOG_KEY, JSON.stringify({ symbols: merged, updatedAt: now }));
          } catch (_) { /* ignore */ }
        }
      } catch (_) { /* ignore */ }
      setCatalogLoaded(true);
      setCatalogUpdatedAt(Date.now());
    };
    ensureCatalog();

    const list = allSymbols;
    let results = list
      .filter(c => typeof c === 'string' && c.toLowerCase().includes(term))
      .slice(0, 8);
    // Fallback: allow direct symbol entry when not found in catalog
    const candidate = term.toUpperCase();
    const validCandidate = /^[A-Z0-9]{2,10}$/.test(candidate);
    if (results.length === 0 && validCandidate && !inSet.has(candidate)) {
      results = [candidate];
    }
    setSearchResults(results);
    setSearchError(results.length === 0 ? 'No coins found or already in watchlist.' : null);
     
  }, [search, symbols.join('|'), allSymbols.length, catalogLoaded]);

  const handleAddFromSearch = async (symbol) => {
    try {
      setLoading(true);
      // Prefer WS cached price; fallback to Coinbase spot fetch
      let currentPrice = null;
      if (latestData && latestData.prices && latestData.prices[symbol]) {
        currentPrice = latestData.prices[symbol].price;
      } else if (latestData && Array.isArray(latestData.crypto)) {
        const hit = latestData.crypto.find((c) => (c.symbol?.replace('-USD','') || c.symbol) === symbol);
        if (hit) currentPrice = hit.current_price ?? hit.price ?? null;
      }
      if (currentPrice == null) {
        try {
          const priceRes = await fetch(`https://api.coinbase.com/v2/prices/${symbol}-USD/spot`);
          const priceJson = await priceRes.json();
          currentPrice = priceJson?.data?.amount ? parseFloat(priceJson.data.amount) : null;
        } catch (_) { /* ignore */ }
      }
      const updated = await addToWatchlist(symbol, currentPrice);
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

  // Keep watchlistData updated from WebSocket cache first
  useEffect(() => {
    if (!symbols.length) { setWatchlistData({}); return; }
    const map = {};
    symbols.forEach((s) => {
      if (latestData?.prices?.[s]) {
          map[s] = { price: latestData.prices[s].price, change: latestData.prices[s].changePercent ?? latestData.prices[s].change ?? null };
        } else if (Array.isArray(latestData?.crypto)) {
          const hit = latestData.crypto.find((c) => (c.symbol?.replace('-USD','') || c.symbol) === s);
          if (hit) {
            const nr = normalizeTableRow(hit);
            map[s] = { price: nr.currentPrice ?? nr._raw?.current_price ?? nr._raw?.price ?? null, change: nr.priceChange1h ?? nr._raw?.price_change_percentage_1min ?? nr._raw?.change ?? null };
          }
        }
    });
    setWatchlistData((prev) => ({ ...prev, ...map }));
     
  }, [latestData, symbols.join('|')]);

  // Fallback: refresh any missing prices every ~60s via Coinbase
  useEffect(() => {
    let timer;
    const refreshMissing = async () => {
      if (!symbols.length) return;
      const updates = {};
      await Promise.all(symbols.map(async (s) => {
        if (watchlistData[s]?.price != null && (isConnected || isPolling)) return; // already filled from WS/polling
        try {
          const res = await fetch(`https://api.coinbase.com/v2/prices/${s}-USD/spot`);
          const j = await res.json();
          const p = j?.data?.amount ? parseFloat(j.data.amount) : null;
          if (p != null) updates[s] = { price: p, change: null };
        } catch (_) { /* ignore */ }
      }));
      if (Object.keys(updates).length > 0) setWatchlistData(prev => ({ ...prev, ...updates }));
    };
    refreshMissing();
    timer = setInterval(refreshMissing, 60000);
    return () => clearInterval(timer);
     
  }, [symbols.join('|'), isConnected, isPolling]);

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
    <div className="flex flex-col space-y-4 w-full h-full min-h-[420px] px-0 align-stretch">
      {/* Always-visible search + add */}
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
            {searchResults.map(symbol => {
              const inWatch = symbols.includes(symbol);
              return (
                <div
                  key={symbol}
                  className="px-4 py-2 hover:bg-purple-900/30 cursor-pointer text-white text-base flex items-center justify-between"
                  onClick={() => handleAddFromSearch(symbol)}
                >
                  <span>{symbol}</span>
                  {inWatch && (
                    <span className="text-[11px] px-2 py-0.5 rounded-full bg-purple-900/50 text-purple-200 border border-purple-800">In Watchlist</span>
                  )}
                </div>
              );
            })}
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
        <React.Fragment>
          {watchlist.length > 0 && (
            <>
              {(showAll ? symbols : symbols.slice(0, 4)).map((symbol, idx) => {
                const data = watchlistData[symbol] || {};
                const pNow = typeof data.price === 'number' ? data.price : null;
                const price = pNow != null ? formatPrice(pNow) : '--';
                const pAdd = Number(priceAtAddMap[symbol]) || 0;
                const prevPrice = pAdd > 0 ? formatPrice(pAdd) : '--';
                const pct = (pAdd > 0 && pNow != null) ? ((pNow - pAdd) / pAdd) * 100 : null;
                const change = pct != null ? `${pct.toFixed(3)}%` : '--';
                const changeColor = pct == null ? 'text-gray-400' : (pct >= 0 ? 'text-purple' : 'text-pink');
                return (
                  <div key={symbol} className="relative group">
                    <div
                      className={
                        `relative overflow-hidden rounded-xl p-4 h-[96px] transition-transform will-change-transform cursor-pointer ` +
                        `group-hover:scale-[1.02] group-hover:z-10 ` +
                        (popStar === symbol ? ' animate-star-pop' : '')
                      }
                      onClick={() => window.open(`https://www.coinbase.com/advanced-trade/spot/${symbol.toLowerCase()}-USD`, '_blank', 'noopener')}
                      role="link"
                      tabIndex={0}
                      onKeyDown={(e)=>{ if(e.key==='Enter'){ window.open(`https://www.coinbase.com/advanced-trade/spot/${symbol.toLowerCase()}-USD`, '_blank', 'noopener'); } }}
                    >
                      {/* Bottom edge subtle diamond glow (purple) to match style */}
                      <span aria-hidden className="pointer-events-none absolute left-0 right-0 bottom-0 h-2 z-0">
                        <span
                          className="block w-full h-full"
                          style={{
                            background:
                              'radial-gradient(ellipse at 50% 140%, rgba(192,38,211,0.18) 0%, rgba(192,38,211,0.10) 35%, rgba(192,38,211,0.04) 60%, transparent 85%)'
                          }}
                        />
                      </span>

                      <div className="relative z-10 grid grid-cols-[minmax(0,1fr)_152px_108px_28px] gap-x-4 items-start">
                        {/* Col1: symbol */}
                        <div className="min-w-0 flex items-center gap-2">
                          <div className="font-bold text-white text-lg tracking-wide truncate">{symbol}</div>
                          {removedBadge === symbol && (
                            <span className="px-2 py-0.5 rounded bg-blue/80 text-white text-xs font-bold animate-fade-in-out shadow-blue-400/30">Removed!</span>
                          )}
                        </div>

                        {/* Col2: current + previous price stacked */}
                        <div className="w-[152px] pr-6 text-right">
                          <div className="text-base sm:text-lg md:text-xl font-bold text-teal font-mono tabular-nums leading-none whitespace-nowrap">
                            {price}
                          </div>
                          <div className="text-sm leading-tight text-gray-300 font-mono tabular-nums whitespace-nowrap">
                            {prevPrice}
                          </div>
                        </div>

                        {/* Col3: % since add */}
                        <div className="w-[108px] pr-1.5 text-right align-top">
                          <div className={`text-lg sm:text-xl md:text-2xl font-bold tabular-nums leading-none whitespace-nowrap ${changeColor}`}>
                            {change}
                          </div>
                          <div className="text-xs text-gray-400 leading-tight">Since add</div>
                        </div>

                        {/* Col4: delete */}
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
                    {/* Removed yellow gradient divider for a cleaner look */}
                  </div>
                );
              })}
              {symbols.length > 4 && (
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

export default Watchlist;
