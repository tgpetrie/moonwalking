import React, { useEffect, useState } from 'react';
import { API_ENDPOINTS, fetchData, addToWatchlist, removeFromWatchlist } from '../api.js';
import StarIcon from './StarIcon.jsx';

const GainersTable1Min = ({
  refreshTrigger,
  onWatchlistChange,
  topWatchlist,
  sliceStart = 0,
  sliceEnd = 20,
  fixedRows,
}) => {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showMore, setShowMore] = useState(false);

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      try {
        const response = await fetchData(API_ENDPOINTS.gainersTable1Min);
        if (response && Array.isArray(response.data)) {
          setData(response.data);
        }
      } catch (error) {
        console.error("Error fetching 1-min gainers:", error);
        setData([]);
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, [refreshTrigger]);

  const handleToggleWatchlist = async (symbol, price) => {
    const isWatched = topWatchlist.includes(symbol);
    const result = isWatched
      ? await removeFromWatchlist(symbol)
      : await addToWatchlist(symbol, price);
    onWatchlistChange(result.watchlist);
    const rawSymbol = item && item.symbol ? item.symbol : '';
    const symbol = rawSymbol.replace('-USD', '') || 'N/A';
    const isWatched = Array.isArray(topWatchlist) && topWatchlist.includes(symbol);
  if (loading) {
    return <div className="text-center text-sm text-gray-400 py-4 animate-pulse">Loading 1-min gainers...</div>;
  }

  const slicedData = data.slice(sliceStart, sliceEnd);

  if (!slicedData.length) {
    return <div className="text-center text-sm text-gray-400 py-4">No 1-min gainers data in this range.</div>;
  }

  // For 1-min gainers we want a side-by-side layout for top 8 (1-4 left, 5-8 right)
  const topEight = slicedData.slice(0, 8);
  const leftCol = topEight.slice(0, 4);
  const rightCol = topEight.slice(4, 8);

  const renderCard = (item, idx, globalIndex) => {
    const symbol = item.symbol.replace('-USD', '');
    const isWatched = topWatchlist.includes(symbol);
    const price = Number(item.current_price || item.price || 0);
    const change = Number(item.price_change_percentage_1min || 0);
    // peak: use provided peak or fallback to small integer derived from change magnitude
    const peak = Math.max(0, Math.min(6, Number(item.peak || item.peak_level || Math.round(Math.abs(change))) || 0));
    return (
      <div key={symbol} className="relative group">
        <a href={`https://www.coinbase.com/advanced-trade/spot/${symbol.toLowerCase()}-USD`} target="_blank" rel="noopener noreferrer" className="block">
          <div className={`table-card flex items-center justify-between`} style={{ boxShadow: '0 2px 12px 0 rgba(129,9,150,0.06)' }}>
            <div className="flex items-center gap-4">
              <div className="flex items-center flex-col justify-center">
                <div className="text-xs text-gray-400 numeric">{globalIndex}</div>
                {/* peak indicator: tiny horizontal bar whose width equals peak px */}
                <div className="mt-1" style={{height:'6px'}}>
                  <div style={{width:`${peak}px`, height:'6px', background:'#810996', borderRadius:2, opacity:0.9}} />
                </div>
              </div>
              <div className="flex-1 flex items-center gap-3">
                <span className="font-bold text-white text-lg tracking-wide">{symbol}</span>
              </div>
            </div>

            <div className="flex flex-row items-center gap-3 sm:gap-4 w-full sm:w-auto">
    const isWatched = Array.isArray(topWatchlist) && topWatchlist.includes(symbol);
                <span className="text-base sm:text-lg md:text-xl font-bold text-teal numeric">{price < 1 && price > 0 ? `$${price.toFixed(4)}` : `$${price.toFixed(2)}`}</span>
                <span className="text-xs sm:text-sm md:text-base font-light text-gray-400">1-min</span>
              </div>
    if (typeof onWatchlistChange === 'function') onWatchlistChange(result.watchlist);
                <div className={`flex items-center gap-1 font-bold text-base sm:text-lg md:text-xl ${change >= 0 ? 'text-purple' : 'text-red-400'}`}>
                  <span className="numeric">{typeof change === 'number' ? `${change.toFixed(2)}%` : 'N/A'}</span>
                </div>
              </div>
              <button onClick={(e) => { e.preventDefault(); handleToggleWatchlist(symbol, price); }} className="bg-transparent border-none p-0 m-0 cursor-pointer" aria-label={isWatched ? `Remove ${symbol} from watchlist` : `Add ${symbol} to watchlist`}>
                <StarIcon filled={isWatched} />
              </button>
            </div>
          </div>
        </a>
      </div>
    );
  };

  return (
    <div className="w-full">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
        <div className="space-y-1">
          {leftCol.map((item, i) => renderCard(item, i, sliceStart + i + 1))}
        </div>
        <div className="space-y-1">
          {rightCol.map((item, i) => renderCard(item, i + 4, sliceStart + i + 5))}
        </div>
      </div>

      {/* Show more toggles: when expanded, show the remaining sliced data in the uniform card style */}
      {showMore && (
        <div className="mt-3 space-y-1">
          {slicedData.slice(8).map((item, idx) => renderCard(item, idx, sliceStart + 9 + idx))}
        </div>
      )}

      {slicedData.length > 8 && (
        <div className="mt-3 flex justify-center">
          <button onClick={() => setShowMore(s => !s)} className="px-3 py-2 rounded bg-purple text-white font-semibold">
            {showMore ? 'Show less' : `Show more (${slicedData.length - 8})`}
          </button>
        </div>
      )}
    </div>
  );
};

export default GainersTable1Min;