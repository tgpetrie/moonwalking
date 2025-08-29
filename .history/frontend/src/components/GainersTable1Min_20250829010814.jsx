import React, { useEffect, useRef, useState } from 'react';
import PropTypes from 'prop-types';
import { API_ENDPOINTS, fetchData, addToWatchlist, removeFromWatchlist } from '../api.js';
import UniformCard from './UniformCard.jsx';
import { useStaggeredPolling } from '../hooks/useStaggeredPolling';
import { useStaggeredRows } from '../hooks/useStaggeredRows';

const GainersTable1Min = ({
  refreshTrigger,
  onWatchlistChange,
  topWatchlist = [],
  sliceStart = 0,
  sliceEnd = 20,
}) => {
  const [data, setData] = useState([]); // full polled list
  const [loading, setLoading] = useState(true);
  const [showMore, setShowMore] = useState(false);
  const prevMapRef = useRef({});

  // Poll 1-min endpoint every 15s (server cadence) with offset so it does not align exactly with 3-min tables burst
  const fetcher = async () => {
    const response = await fetchData(API_ENDPOINTS.gainersTable1Min);
    if (!response || !Array.isArray(response.data)) return [];
    const rows = response.data.map((item, idx) => {
      const rawSymbol = item?.symbol || '';
      const symbol = rawSymbol.replace('-USD', '');
      const price = Number(item?.current_price ?? item?.price ?? 0);
      const change = Number(item?.price_change_percentage_1min ?? item?.gain ?? 0);
      const peak = Number(item?.peak || item?.peak_level || 0);
      return { symbol, price, change, peak, rank: idx + 1 };
    }).slice(sliceStart, sliceEnd);
    const annotated = rows.map(r => {
      const prev = prevMapRef.current[r.symbol];
      const diffDir = prev && typeof prev.change === 'number' && typeof r.change === 'number'
        ? (r.change > prev.change ? 'up' : r.change < prev.change ? 'down' : 'flat')
        : 'flat';
      return { ...r, diffDir };
    });
    const newMap = {};
    annotated.forEach(r => { newMap[r.symbol] = r; });
    prevMapRef.current = newMap;
    return annotated;
  };

  const { data: polled, loading: pollLoading, error: pollError } = useStaggeredPolling(fetcher, {
    interval: 15000, // 15s
    offset: 2500, // start ~2.5s after load to avoid immediate burst overlap
    jitter: 1200,
    active: true
  });

  // Progressive reveal (slightly faster per row for urgency feel)
  const visible = useStaggeredRows(polled || [], 30, 0);

  useEffect(() => {
    if (pollError) {
      console.error('1-min poll error:', pollError);
    }
    if (Array.isArray(polled)) {
      setData(polled);
    }
    setLoading(pollLoading && (!polled || polled.length === 0));
  }, [polled, pollLoading, pollError]);

  // Reset diff history on external trigger (optional manual refresh)
  useEffect(() => { prevMapRef.current = {}; }, [refreshTrigger]);

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

  if (!visible.length) {
    return <div className="text-center text-sm text-gray-400 py-4">No 1-min gainers data in this range.</div>;
  }

  const topEight = visible.slice(0, 8);
  const leftCol = topEight.slice(0, 4);
  const rightCol = topEight.slice(4, 8);

  return (
    <div className="w-full">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-2" style={{ gridAutoRows: 'minmax(0, 1fr)' }}>
        <div className="space-y-1">
          {leftCol.map((item, i) => {
            const isWatched = Array.isArray(topWatchlist) && topWatchlist.some((w) => (typeof w === 'string' ? w === item.symbol : w.symbol === item.symbol));
            return (
              <UniformCard
                key={`${item.symbol}-L-${i}`}
                symbol={item.symbol}
                price={item.price}
                change={item.change}
                rank={item.rank}
                peak={item.peak}
                showPeak={true}
                windowLabel="1-min"
                filled={isWatched}
                onToggle={handleToggleWatchlist}
                percentClassName={item.diffDir === 'up' ? 'value-flash-up' : item.diffDir === 'down' ? 'value-flash-down' : ''}
              />
            );
          })}
        </div>
        <div className="space-y-1">
          {rightCol.map((item, i) => {
            const isWatched = Array.isArray(topWatchlist) && topWatchlist.some((w) => (typeof w === 'string' ? w === item.symbol : w.symbol === item.symbol));
            return (
              <UniformCard
                key={`${item.symbol}-R-${i}`}
                symbol={item.symbol}
                price={item.price}
                change={item.change}
                rank={item.rank}
                peak={item.peak}
                showPeak={true}
                windowLabel="1-min"
                filled={isWatched}
                onToggle={handleToggleWatchlist}
                percentClassName={item.diffDir === 'up' ? 'value-flash-up' : item.diffDir === 'down' ? 'value-flash-down' : ''}
              />
            );
          })}
        </div>
      </div>

      {showMore && (
        <div className="mt-3 space-y-1">
          {visible.slice(8).map((item, idx) => {
            const isWatched = Array.isArray(topWatchlist) && topWatchlist.some((w) => (typeof w === 'string' ? w === item.symbol : w.symbol === item.symbol));
            return (
              <UniformCard
                key={`${item.symbol}-X-${idx}`}
                symbol={item.symbol}
                price={item.price}
                change={item.change}
                rank={item.rank}
                showPeak={false}
                windowLabel="1-min"
                filled={isWatched}
                onToggle={handleToggleWatchlist}
                percentClassName={item.diffDir === 'up' ? 'value-flash-up' : item.diffDir === 'down' ? 'value-flash-down' : ''}
              />
            );
          })}
        </div>
      )}

      {visible.length > 8 && (
        <div className="mt-3 flex justify-center">
          <button onClick={() => setShowMore((s) => !s)} className="px-3 py-2 rounded bg-purple text-white font-semibold">
            {showMore ? 'Show less' : `Show more (${visible.length - 8})`}
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
};
