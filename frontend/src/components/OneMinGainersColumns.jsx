import React, { useEffect, useState } from 'react';
import { useWebSocket } from '../context/websocketcontext.jsx';
import { API_ENDPOINTS, fetchData } from '../api.js';
import formatSymbol from '../lib/format.js';
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
      // Prefer WS snapshot; fallback to API
      let source = Array.isArray(latestData?.crypto) ? latestData.crypto : null;
      if (!source || source.length === 0) {
        try {
          const res = await fetchData(API_ENDPOINTS.gainersTable1Min);
          source = Array.isArray(res?.data) ? res.data : [];
        } catch (_) {
          source = [];
        }
      }
      const mapped = (source || []).map((item, idx) => {
        const raw = item.peak_gain ?? item.price_change_percentage_1min ?? item.change ?? 0;
        const abs = Math.abs(Number(raw) || 0);
        const needsScale = abs > 0 && abs < 0.02;
        const pct = needsScale ? Number(raw) * 100 : Number(raw) || 0;
        return ({
          rank: item.rank || idx + 1,
          symbol: formatSymbol(item.symbol) || 'N/A',
          price: item.current_price ?? item.price ?? 0,
          change: pct,
          initial_price_1min: item.initial_price_1min ?? item.initial_1min ?? null,
          peakCount: typeof item.peak_count === 'number' ? item.peak_count : (typeof item.trend_streak === 'number' ? item.trend_streak : 0),
        });
      });
      // Dedupe by symbol, keep highest change
      const bySym = new Map();
      for (const r of mapped) {
        const prev = bySym.get(r.symbol);
        if (!prev || Math.abs(r.change) > Math.abs(prev.change)) bySym.set(r.symbol, r);
      }
      const unique = Array.from(bySym.values());
      const sorted = unique.sort((a, b) => (b.change - a.change));
      const total = expanded ? 12 : 8;
      const top = sorted.slice(0, total).map((it, i) => ({ ...it, rank: i + 1 }));
      const half = Math.floor(top.length / 2);
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
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 w-full">
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
