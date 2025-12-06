import React, { useState, useEffect } from 'react';
import { getWatchlist, addToWatchlist, removeFromWatchlist } from '../api.js';
import TokenRow from './TokenRow.jsx';
import PanelShell from './ui/PanelShell';
import StatusGate from './ui/StatusGate';
import SkeletonTable from './ui/SkeletonTable';

export default function Watchlist({ onWatchlistChange, topWatchlist, quickview, onInfo }) {
  const [showAll, setShowAll] = useState(false);
  const [search, setSearch] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [searchError, setSearchError] = useState(null);
  const [watchlist, setWatchlist] = useState(topWatchlist || []);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [watchlistData, setWatchlistData] = useState({});

  const COIN_LIST = [
    'BTC','ETH','SOL','ADA','XRP','DOGE','LTC','AVAX','DOT','ATOM','NEAR','PEPE','SHIB','FLOKI','BONK','WIF','SEI','BNB','LINK','MATIC','ARB','OP','TIA','RNDR','UNI','AAVE','SUI','JUP','PYTH','USDT','USDC','WBTC','TRX','BCH','ETC','FIL','STX','IMX','MKR','GRT','LDO','INJ','RUNE','DYDX','CAKE','SAND','AXS','MANA','APE','GMT','ENS','1INCH','COMP','CRV','SNX','YFI','ZRX','BAT','KNC','BAL','CVX','SUSHI','UMA','BNT','REN','SRM','ALGO','CRO','FTM','KAVA','MINA','XLM','VET','HBAR','QNT','EGLD','XTZ','CHZ','GALA','FLOW','ENJ','ANKR','CELO','CKB','DASH','RVN','ZIL','ICX','ONT','QTUM','SC','WAVES','XEM','ZEN','ZEC','LSK','STEEM','BTS','ARDR','STRAX','SYS','NXT','FCT','DCR','GAME','BLOCK','NAV','VTC','PIVX','XVG','EXP','NXS','NEO','GAS','DGB','BTG','XMR'
  ];

  useEffect(() => {
    if (typeof search !== 'string' || search.trim() === '') {
      setSearchResults([]);
      setSearchError(null);
      return;
    }
    const results = COIN_LIST.filter(c => typeof c === 'string' && c.toLowerCase().includes(search.trim().toLowerCase()) && !watchlist.includes(c)).slice(0,8);
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

  const fetchWatchlistLocal = async () => {
    try {
      setLoading(true);
      const data = await getWatchlist();
      setWatchlist(data);
      if (onWatchlistChange) onWatchlistChange(data);
    } catch (err) {
      setError(err.message || 'Failed to fetch watchlist');
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
      fetchWatchlistLocal();
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
        results.forEach(({ symbol, price, change }) => { map[symbol] = { price, change }; });
        setWatchlistData(map);
      } catch (err) {
        setWatchlistData({});
      }
    };
    fetchAllData();
  }, [watchlist]);

  const handleRemove = async (symbol) => {
    try {
      setLoading(true);
      const data = await removeFromWatchlist(symbol);
      setWatchlist(data);
      if (onWatchlistChange) onWatchlistChange(data);
    } catch (err) {
      setError(err.message || `Failed to remove ${symbol}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <PanelShell title="WATCHLIST">
      <div className={`watchlist-input ${loading ? 'is-loading' : ''}`}>
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
      </div>

      <StatusGate
        status={
          error ? 'error' :
          watchlist.length > 0 ? 'ready' :
          loading ? 'loading' : 'empty'
        }
        skeleton={<SkeletonTable rows={3} />}
        empty={<div className="state-copy">Star a token to pin it here.</div>}
        error={<div className="state-copy">Watchlist unavailable.</div>}
      >
        <div className="flex flex-col space-y-4 w-full max-w-4xl mx-auto h-full min-h-[420px] px-1 sm:px-3 md:px-0 align-stretch">
          {(showAll ? watchlist : watchlist.slice(0, 4)).map((symbol, idx) => {
            const data = watchlistData[symbol] || {};
            const current = data.price ?? null;
            // Watchlist doesn't have a previous price source here; leave null
            const previous = null;
            return (
              <div key={symbol}>
                <TokenRow
                  rank={idx + 1}
                  symbol={symbol}
                  name={null}
                  currentPrice={current}
                  previousPrice={previous}
                  percentChange={0}
                  onToggleWatchlist={() => handleRemove(symbol)}
                  onInfo={() => onInfo && onInfo(symbol)}
                  isWatchlisted={true}
                />
                {idx < (showAll ? watchlist.length : Math.min(4, watchlist.length)) - 1 && (
                  <div className="mx-auto my-0.5" style={{height:'2px',width:'60%',background:'linear-gradient(90deg,rgba(254,164,0,0.18) 0%,rgba(254,164,0,0.38) 50%,rgba(254,164,0,0.18) 100%)',borderRadius:'2px'}} />
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
        </div>
      </StatusGate>
    </PanelShell>
  );
}
