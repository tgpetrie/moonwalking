import React, { useEffect, useState } from 'react';
import PropTypes from 'prop-types';
import { API_ENDPOINTS, fetchData, addToWatchlist, removeFromWatchlist } from '../api.js';
import UniformCard from './UniformCard.jsx';

const GainersTable1Min = ({
  refreshTrigger,
  onWatchlistChange,
  topWatchlist = [],
  sliceStart = 0,
  sliceEnd = 20,
}) => {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showMore, setShowMore] = useState(false);

  useEffect(() => {
    let mounted = true;
    const loadData = async () => {
      setLoading(true);
      try {
        const response = await fetchData(API_ENDPOINTS.gainersTable1Min);
        if (response && Array.isArray(response.data)) {
          if (mounted) setData(response.data);
        } else {
          if (mounted) setData([]);
        }
      } catch (error) {
        console.error('Error fetching 1-min gainers:', error);
        if (mounted) setData([]);
      } finally {
        if (mounted) setLoading(false);
      }
    };
    loadData();
    return () => { mounted = false; };
  }, [refreshTrigger]);

  const handleToggleWatchlist = async (symbol, price) => {
    const isWatched = Array.isArray(topWatchlist) && topWatchlist.some((w) => (typeof w === 'string' ? w === symbol : w.symbol === symbol));
    const result = isWatched
      ? await removeFromWatchlist(symbol)
      : await addToWatchlist(symbol, price);
    if (typeof onWatchlistChange === 'function') {
      onWatchlistChange(result || []);
    }
  };

  if (loading) {
    return <div className="text-center text-sm text-gray-400 py-4 animate-pulse">Loading 1-min gainers...</div>;
  }

  const slicedData = Array.isArray(data) ? data.slice(sliceStart, sliceEnd) : [];

  if (!slicedData.length) {
    return <div className="text-center text-sm text-gray-400 py-4">No 1-min gainers data in this range.</div>;
  }

  const topEight = slicedData.slice(0, 8);
  const leftCol = topEight.slice(0, 4);
  const rightCol = topEight.slice(4, 8);

  return (
    <div className="w-full">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-2" style={{ gridAutoRows: 'minmax(0, 1fr)' }}>
        <div className="space-y-1">
          {leftCol.map((item, i) => {
            const rawSymbol = item && item.symbol ? item.symbol : '';
            const symbol = rawSymbol.replace('-USD', '');
            const price = Number(item && (item.current_price || item.price) || 0);
            const change = Number(item && (item.price_change_percentage_1min) || 0);
            const peak = Math.max(0, Math.min(6, Number(item && (item.peak || item.peak_level) || Math.round(Math.abs(change))) || 0));
            const rank = sliceStart + i + 1;
            const isWatched = Array.isArray(topWatchlist) && topWatchlist.some((w) => (typeof w === 'string' ? w === symbol : w.symbol === symbol));
            return (
              <UniformCard
                key={`${symbol}-${rank}`}
                symbol={symbol}
                price={price}
                change={change}
                rank={rank}
                peak={peak}
                showPeak={true}
                windowLabel="1-min"
                filled={isWatched}
                onToggle={handleToggleWatchlist}
              />
            );
          })}
        </div>
        <div className="space-y-1">
          {rightCol.map((item, i) => {
            const rawSymbol = item && item.symbol ? item.symbol : '';
            const symbol = rawSymbol.replace('-USD', '');
            const price = Number(item && (item.current_price || item.price) || 0);
            const change = Number(item && (item.price_change_percentage_1min) || 0);
            const peak = Math.max(0, Math.min(6, Number(item && (item.peak || item.peak_level) || Math.round(Math.abs(change))) || 0));
            const rank = sliceStart + i + 5;
            const isWatched = Array.isArray(topWatchlist) && topWatchlist.some((w) => (typeof w === 'string' ? w === symbol : w.symbol === symbol));
            return (
              <UniformCard
                key={`${symbol}-${rank}`}
                symbol={symbol}
                price={price}
                change={change}
                rank={rank}
                peak={peak}
                showPeak={true}
                windowLabel="1-min"
                filled={isWatched}
                onToggle={handleToggleWatchlist}
              />
            );
          })}
        </div>
      </div>

      {showMore && (
        <div className="mt-3 space-y-1">
          {slicedData.slice(8).map((item, idx) => {
            const rawSymbol = item && item.symbol ? item.symbol : '';
            const symbol = rawSymbol.replace('-USD', '');
            const price = Number(item && (item.current_price || item.price) || 0);
            const change = Number(item && (item.price_change_percentage_1min) || 0);
            const rank = sliceStart + 9 + idx;
            const isWatched = Array.isArray(topWatchlist) && topWatchlist.some((w) => (typeof w === 'string' ? w === symbol : w.symbol === symbol));
            return (
              <UniformCard
                key={`${symbol}-${rank}`}
                symbol={symbol}
                price={price}
                change={change}
                rank={rank}
                showPeak={false}
                windowLabel="1-min"
                filled={isWatched}
                onToggle={handleToggleWatchlist}
              />
            );
          })}
        </div>
      )}

      {slicedData.length > 8 && (
        <div className="mt-3 flex justify-center">
          <button onClick={() => setShowMore((s) => !s)} className="px-3 py-2 rounded bg-purple text-white font-semibold">
            {showMore ? 'Show less' : `Show more (${slicedData.length - 8})`}
          </button>
        </div>
      )}
    </div>
  );
};

GainersTable1Min.propTypes = {
  refreshTrigger: PropTypes.any,
  onWatchlistChange: PropTypes.func,
  topWatchlist: PropTypes.array,
  sliceStart: PropTypes.number,
  sliceEnd: PropTypes.number,
  // optional props used elsewhere in the app
};

export default GainersTable1Min;
import React, { useEffect, useRef, useState } from 'react';
import { API_ENDPOINTS, fetchData, getWatchlist, addToWatchlist } from '../api.js';
import { formatPercentage, truncateSymbol } from '../utils/formatters.js';
import { useWebSocket } from '../context/websocketcontext.jsx';
import StarIcon from './StarIcon';
import TableShell from './TableShell';
import PriceFlash from './PriceFlash';
  return (
    <div className="w-full h-full min-h-[420px] px-1 sm:px-3 md:px-0 transition-all duration-300">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {visibleData.slice(0, rowsToShow).map((item) => {
          const coinbaseUrl = `https://www.coinbase.com/advanced-trade/spot/${item.symbol.toLowerCase()}-USD`;
          const isInWatchlist = watchlist.some((w) => (typeof w === 'string' ? w === item.symbol : w.symbol === item.symbol));
          const isPopping = popStar === item.symbol;
          const showAdded = addedBadge === item.symbol;
          const PCT = item.change;
          const INTERVAL_LABEL = '1-min';
          const inWatch = isInWatchlist;
          const toggleWatch = (sym) => handleToggleWatchlist(sym);

          return (
            <div key={item.symbol} className="crypto-row flex items-center px-2 py-1 rounded-lg transition h-full">
              <a href={coinbaseUrl} target="_blank" rel="noopener noreferrer" className="block group flex-1 h-full">
                <div className="flex flex-col h-full">
                  <div
                    className="p-4 rounded-xl transition-all duration-300 cursor-pointer relative overflow-hidden group hover:scale-[1.02] sm:hover:scale-[1.035] hover:z-10 h-full"
                    style={{ background: 'transparent' }}
                  >
                    {/* PURPLE INNER GLOW (#C026D3) */}
                    <span className="pointer-events-none absolute inset-0 flex items-center justify-center z-0">
                      <span
                        className="block rounded-xl transition-all duration-500 opacity-0 group-hover:opacity-90 w-[130%] h-[130%] group-hover:w-[165%] group-hover:h-[165%]"
                        style={{
                          background: 'radial-gradient(circle at 50% 50%, rgba(192,38,211,0.20) 0%, rgba(192,38,211,0.12) 45%, rgba(192,38,211,0.06) 70%, transparent 100%)',
                          top: '-15%',
                          left: '-15%',
                          position: 'absolute',
                          mixBlendMode: 'normal',
                        }}
                      />
                    </span>

                    {/* MAIN ROW — use TableShell for consistent column sizing */}
                    <TableShell className="items-center">
                      {/* LEFT flexible: rank + symbol */}
                      <div className="flex items-center gap-3 sm:gap-4 min-w-0">
                        <div className="flex items-center justify-center w-8 h-8 rounded-full bg-[#C026D3]/40 text-[#C026D3] font-bold text-sm shrink-0">{item.rank}</div>
                        <div className="min-w-0 flex items-center gap-3">
                          <span className="font-bold text-white text-lg tracking-wide truncate">{truncateSymbol(item.symbol, 8)}</span>
                          {showAdded && (
                            <span className="px-2 py-0.5 rounded bg-blue/80 text-white text-xs font-bold animate-fade-in-out shadow-blue-400/30">Added!</span>
                          )}
                        </div>
                      </div>

                      {/* Col2: Price (stack current + previous) */}
                      <div className="w-[152px] pr-6 text-right">
                        {Number.isFinite(item.price) ? (
                          <PriceFlash
                            value={item.price}
                            precision={item.price < 1 && item.price > 0 ? 4 : 2}
                            className="text-teal font-mono text-base sm:text-lg md:text-xl font-bold tabular-nums leading-none"
                          />
                        ) : (
                          export default GainersTable1Min;