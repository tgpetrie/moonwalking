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
                          <div className="text-base sm:text-lg md:text-xl font-bold text-teal font-mono tabular-nums leading-none">N/A</div>
                        )}
                        <div className="text-sm leading-tight text-gray-300 font-mono tabular-nums whitespace-nowrap">
                          {formatPrev(item.price, PCT)}
                        </div>
                      </div>

                      {/* Col3: % (stack % → Peak → interval) */}
                      <div className="w-[108px] pr-1.5 text-right align-top">
                        <OneMinPercentCell value={PCT} peak={item.peakCount} interval={INTERVAL_LABEL} />
                      </div>

                      {/* Col4: Star (action area) */}
                      <div className="w-[48px] text-right">
                        <button
                          onClick={(e)=>{e.preventDefault(); toggleWatch(item.symbol);}}
                          className="bg-transparent border-none p-0 m-0 cursor-pointer inline-flex items-center justify-end"
                          style={{ minWidth:'24px', minHeight:'24px' }}
                          aria-label={inWatch ? 'Remove from watchlist' : 'Add to watchlist'}
                          aria-pressed={inWatch}
                        >
                          <StarIcon
                            filled={inWatch}
                            className={inWatch ? 'opacity-80 hover:opacity-100' : 'opacity-40 hover:opacity-80'}
                            style={{ width:'16px', height:'16px', transition:'transform .2s' }}
                            aria-hidden="true"
                          />
                        </button>
                      </div>
                    </TableShell>
                  </div>
                </div>
              </a>
            </div>
          );
        })}
      </div>

      {!hideShowMore && Array.isArray(visibleData) && visibleData.length > 8 && (
        <div className="mt-3 flex justify-center">
          <button
            className="px-4 py-1 rounded bg-blue-900 text-white text-xs font-bold hover:bg-blue-700 transition"
            style={{ width: 'fit-content' }}
            onClick={() => setShowAll((s) => !s)}
          >
            {showAll ? 'Show Less' : `Show More (${Math.max(0, Math.min(12, visibleData.length) - 8)})`}
          </button>
        </div>
      )}
    </div>
  );
    const exists = watchlist.some((it) => (typeof it === 'string' ? it === symbol : it.symbol === symbol));
    if (!exists) {
      setPopStar(symbol);
      setAddedBadge(symbol);
      setTimeout(() => setPopStar(null), 350);
      setTimeout(() => setAddedBadge(null), 1200);
      const coin = data.find((c) => c.symbol === symbol);
      const currentPrice = coin ? coin.price : null;
      const updated = await addToWatchlist(symbol, currentPrice);
      setWatchlist(updated);
      onWatchlistChange && onWatchlistChange(updated);
    }
  };

  const visibleData = Array.isArray(data)
    ? typeof sliceStart === 'number' || typeof sliceEnd === 'number'
      ? data.slice(sliceStart ?? 0, sliceEnd ?? data.length)
      : data
    : [];

  const formatPrev = (price, pct) => {
    if (typeof price === 'number' && typeof pct === 'number' && pct !== 0) {
      const prev = price / (1 + pct / 100);
      return `$${prev < 1 && prev > 0 ? prev.toFixed(4) : prev.toFixed(2)}`;
    }
    return '--';
  };

  // Default: show 8 tiles (two columns of 4). When showAll is true, expand to up to 12.
  const rowsToShow = typeof fixedRows === 'number' && fixedRows > 0
    ? Math.min(fixedRows, visibleData.length)
    : (showAll ? Math.min(12, visibleData.length) : Math.min(8, visibleData.length));

  if (loading && visibleData.length === 0) {
    return (
      <div className="w-full h-full min-h-[420px] px-1 sm:px-3 md:px-0 transition-all duration-300 flex items-center justify-center">
        <div className="animate-pulse text-[#C026D3] font-mono">Loading 1-min gainers...</div>
      </div>
    );
  }

  if (visibleData.length === 0) {
    return (
      <div className="w-full h-full min-h-[420px] px-1 sm:px-3 md:px-0 transition-all duration-300 flex items-center justify-center">
        <div className="text-muted font-mono">No 1-min gainers data available</div>
      </div>
    );
  }

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
              <div
                className="flex flex-col"
              >
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
                        <div className="text-base sm:text-lg md:text-xl font-bold text-teal font-mono tabular-nums leading-none">N/A</div>
                      )}
                      <div className="text-sm leading-tight text-gray-300 font-mono tabular-nums whitespace-nowrap">
                        {formatPrev(item.price, PCT)}
                      </div>
                    </div>

                    {/* Col3: % (stack % → Peak → interval) */}
                    <div className="w-[108px] pr-1.5 text-right align-top">
                      <OneMinPercentCell value={PCT} peak={item.peakCount} interval={INTERVAL_LABEL} />
                    </div>

                    {/* Col4: Star (action area) */}
                    <div className="w-[48px] text-right">
                      <button
                        onClick={(e)=>{e.preventDefault(); toggleWatch(item.symbol);}}
                        className="bg-transparent border-none p-0 m-0 cursor-pointer inline-flex items-center justify-end"
                        style={{ minWidth:'24px', minHeight:'24px' }}
                        aria-label={inWatch ? 'Remove from watchlist' : 'Add to watchlist'}
                        aria-pressed={inWatch}
                      >
                        <StarIcon
                          filled={inWatch}
                          className={inWatch ? 'opacity-80 hover:opacity-100' : 'opacity-40 hover:opacity-80'}
                          style={{ width:'16px', height:'16px', transition:'transform .2s' }}
                          aria-hidden="true"
                        />
                      </button>
                    </div>
                  </TableShell>
                </div>

              </div>
            )}

            {!hideShowMore && Array.isArray(visibleData) && visibleData.length > 8 && (
      })}

      {!hideShowMore && Array.isArray(visibleData) && visibleData.length > 8 && (
        <button
          className="mt-2 mx-auto px-4 py-1 rounded bg-blue-900 text-white text-xs font-bold hover:bg-blue-700 transition"
          style={{ width: 'fit-content' }}
          onClick={() => setShowAll((s) => !s)}
        >
          </div>
        </div>
        </button>
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
  fixedRows: PropTypes.number,
  hideShowMore: PropTypes.bool,
};

export default GainersTable1Min;