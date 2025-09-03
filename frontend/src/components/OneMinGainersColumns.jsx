import React, { useEffect, useState } from 'react';
import PropTypes from 'prop-types';
import { useWebSocket } from '../context/websocketcontext.jsx';
import { API_ENDPOINTS, fetchData } from '../api.js';
import GainersTable1Min from './GainersTable1Min.jsx';

export default function OneMinGainersColumns({
  refreshTrigger,
  onWatchlistChange,
  topWatchlist,
  expanded = false,
}) {
  const { latestData } = useWebSocket();
  const [left, setLeft] = useState([]);
  const [right, setRight] = useState([]);

  useEffect(() => {
    let cancelled = false;
    const build = async () => {
      // Prefer processed gainersTop20 from context if available (already ranked & stable)
      let source = Array.isArray(latestData?.crypto) ? latestData.crypto : [];
      if (!source.length) {
        try {
          const res = await fetchData(API_ENDPOINTS.gainersTable1Min);
          source = Array.isArray(res?.data) ? res.data : [];
        } catch {
          source = [];
        }
      }
      const mapped = source.map((item, idx) => {
        let peakCount = 0;
        if (typeof item.peak_count === 'number') {
          peakCount = item.peak_count;
        } else if (typeof item.trend_streak === 'number') {
          peakCount = item.trend_streak;
        }
        return {
          rank: item.rank || idx + 1,
          symbol: item.symbol?.replace('-USD', '') || 'N/A',
          price: item.current_price ?? item.price ?? 0,
          change: item.peak_gain ?? item.price_change_percentage_1min ?? item.change ?? 0,
          peakCount,
        };
      });
      const bySym = new Map();
      for (const r of mapped) {
        const prev = bySym.get(r.symbol);
        if (!prev || Math.abs(r.change) > Math.abs(prev.change)) {
          bySym.set(r.symbol, r);
        }
      }
      const unique = Array.from(bySym.values()).sort((a,b)=> b.change - a.change);
      const collapsedCount = 10; // show more by default vs previous 8
      const expandedCount = 20;  // full top 20 when expanded
      const target = expanded ? expandedCount : collapsedCount;
      const top = unique.slice(0, target).map((it,i)=> ({ ...it, rank: i+1 }));
      const half = Math.ceil(top.length / 2);
      if (!cancelled) {
        setLeft(top.slice(0, half));
        setRight(top.slice(half));
      }
    };
    build();
    return () => { cancelled = true; };
  }, [refreshTrigger, latestData?.crypto, expanded]);

  // sliceStart controls the displayed rank numbering within the child
  const leftSliceStart = 0;
  const rightSliceStart = left.length; // 4 when collapsed, 6 when expanded

  return (
    <div className="grid grid-cols-1 responsive-grid-2 gap-x-16 gap-y-8 mt-3">
      <GainersTable1Min
        refreshTrigger={refreshTrigger}
        onWatchlistChange={onWatchlistChange}
        topWatchlist={topWatchlist}
        rows={left}
        sliceStart={leftSliceStart}
        sliceEnd={left.length}
        hideShowMore
      />
      <GainersTable1Min
        refreshTrigger={refreshTrigger}
        onWatchlistChange={onWatchlistChange}
        topWatchlist={topWatchlist}
        rows={right}
        sliceStart={rightSliceStart}
        sliceEnd={rightSliceStart + right.length}
        hideShowMore
      />
    </div>
  );
}

OneMinGainersColumns.propTypes = {
  refreshTrigger: PropTypes.any,
  onWatchlistChange: PropTypes.func,
  topWatchlist: PropTypes.array,
  expanded: PropTypes.bool,
};

