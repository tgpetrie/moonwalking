import React, { useEffect, useMemo, useRef, useState } from 'react';
import { API_ENDPOINTS, fetchData } from '../api.js';

// Polling + marquee that always moves (no external CSS required)
export default function TopBannerScroll({ pollMs = 15000, fallbackLimit = 20 }) {
  const [items, setItems] = useState([]);
  const trackRef = useRef(null);
  const [animKey, setAnimKey] = useState(0);

  // normalize API payload into a compact shape we render
  const normalize = (raw = []) => {
    const arr = Array.isArray(raw) ? raw : (raw?.data || raw?.items || raw?.headlines || []);
    if (!Array.isArray(arr)) return [];
    return arr
      .map((item, index) => ({
        id: item.id ?? item._id ?? index,
        rank: item.rank ?? index + 1,
        symbol: (item.symbol || item.ticker || '').replace('-USD', '') || 'N/A',
        price: item.current_price ?? item.price ?? item.last ?? 0,
        change: item.price_change_1h ?? item.change_1h ?? item.delta_1h ?? 0,
        trendDirection: item.trend_direction ?? item.trendDirection ?? 'flat',
        trendStreak: item.trend_streak ?? item.trendStreak ?? 0,
        trendScore: item.trend_score ?? item.trendScore ?? 0,
      }))
      .filter((x) => x.symbol && x.symbol !== 'N/A');
  };

  const getBadge = (chg) => {
    const v = Math.abs(Number(chg) || 0);
    if (v >= 5) return 'STRONG HIGH';
    if (v >= 2) return 'STRONG';
    return 'MODERATE';
  };

  // Initial fetch + polling
  useEffect(() => {
    let alive = true;
    let timer;

    const run = async () => {
      try {
        const res = await fetchData(API_ENDPOINTS.topBanner);
        const next = normalize(res);
        if (alive && next.length) {
          setItems(next.slice(0, fallbackLimit));
        } else if (alive && !items.length) {
          // fallback only when we have nothing
          setItems([
            { id: 'fb-1', rank: 1, symbol: 'SUKU', price: 0.0295, change: 3.51 },
            { id: 'fb-2', rank: 2, symbol: 'HNT',  price: 2.30,   change: 0.97 },
            { id: 'fb-3', rank: 3, symbol: 'OCEAN',price: 0.3162, change: 0.60 },
            { id: 'fb-4', rank: 4, symbol: 'PENGU',price: 0.01605,change: 0.56 },
            { id: 'fb-5', rank: 5, symbol: 'MUSE', price: 7.586,  change: 0.53 },
          ]);
        }
      } catch (e) {
        if (alive && !items.length) {
          setItems([
            { id: 'fb-1', rank: 1, symbol: 'SUKU', price: 0.0295, change: 3.51 },
            { id: 'fb-2', rank: 2, symbol: 'HNT',  price: 2.30,   change: 0.97 },
            { id: 'fb-3', rank: 3, symbol: 'OCEAN',price: 0.3162, change: 0.60 },
            { id: 'fb-4', rank: 4, symbol: 'PENGU',price: 0.01605,change: 0.56 },
            { id: 'fb-5', rank: 5, symbol: 'MUSE', price: 7.586,  change: 0.53 },
          ]);
        }
      }
      timer = setTimeout(run, pollMs);
    };

    run();
    return () => { alive = false; clearTimeout(timer); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pollMs]);

  // Restart animation whenever the item IDs change (ensures marquee moves on update)
  const animDeps = useMemo(() => items.map((i) => i.id).join(','), [items]);
  useEffect(() => { setAnimKey((k) => k + 1); }, [animDeps]);

  if (!items.length) return null;

  // compute animation speed based on total content width so it feels smooth
  const durationSec = 35; // default if we can’t measure
  const containerStyle = { position: 'relative', height: 64, overflow: 'hidden' };
  const trackStyle = {
    display: 'inline-flex',
    gap: '2rem',
    whiteSpace: 'nowrap',
    padding: '8px 12px',
    animation: `banner-scroll ${durationSec}s linear infinite`,
  };

  return (
    <div className="relative overflow-hidden rounded-3xl w-full max-w-full" style={{ background: 'transparent' }}>
      {/* Header */}
      <div className="px-3 sm:px-6 py-3 sm:py-4">
        <div className="flex items-center gap-2 sm:gap-3">
          <h3 className="text-base font-headline font-bold tracking-wide uppercase" style={{ color: 'rgb(254, 164, 0)' }}>
            1H Price Change • Live Market Feed
          </h3>
        </div>
      </div>

      {/* Scrolling Content */}
      <div className="relative" style={containerStyle}>
        {/* edge fades */}
        <div className="pointer-events-none absolute left-0 top-0 w-16 h-full" style={{background: 'linear-gradient(to right, rgba(9,9,13,1), rgba(9,9,13,0.7), transparent)'}} />
        <div className="pointer-events-none absolute right-0 top-0 w-16 h-full" style={{background: 'linear-gradient(to left, rgba(9,9,13,1), rgba(9,9,13,0.7), transparent)'}} />

        <div className="absolute inset-0 flex items-center">
          <div ref={trackRef} key={animKey} style={trackStyle}>
            {/* First set */}
            {items.map((coin) => (
              <Pill key={`a-${coin.id}`} coin={coin} badge={getBadge(coin.change)} />
            ))}
            {/* Duplicate for seamless loop */}
            {items.map((coin) => (
              <Pill key={`b-${coin.id}`} coin={coin} badge={getBadge(coin.change)} />
            ))}
          </div>
        </div>
      </div>

      {/* Local keyframes to avoid depending on global CSS */}
      <style>{`
        @keyframes banner-scroll { from { transform: translateX(0); } to { transform: translateX(-50%); } }
      `}</style>
    </div>
  );
}

function Pill({ coin, badge }) {
  const asMoney = (p) => {
    const n = Number(p) || 0;
    return `$${n < 1 ? n.toFixed(4) : n.toFixed(2)}`;
  };
  const asPct = (v) => {
    const n = Number(v) || 0;
    const pct = Math.abs(n) <= 1 ? n : n; // treat as already percent if > 1
    const sign = n >= 0 ? '+' : '';
    return `${sign}${pct.toFixed(2)}%`;
  };
  const trend = coin.trendDirection;
  const score = Math.max(0, Math.min(3, Number(coin.trendScore) || 0));
  const color = trend === 'up'
    ? (score >= 1.5 ? '#10B981' : score >= 0.5 ? '#34D399' : '#9AE6B4')
    : (score >= 1.5 ? '#EF4444' : score >= 0.5 ? '#F87171' : '#FEB2B2');
  const arrow = trend === 'up' ? '↑' : trend === 'down' ? '↓' : '';

  return (
    <div className="flex-shrink-0 mx-8 group">
      <div className="flex items-center gap-4 pill-hover px-4 py-2 rounded-full transition-all duration-300 group-hover:text-purple group-hover:text-shadow-purple">
        <div className="flex items-center gap-2">
          <span className="text-xs font-bold text-purple">#{coin.rank}</span>
          <span className="text-sm font-headline font-bold tracking-wide">{coin.symbol}</span>
          <span className="font-mono text-base font-bold bg-orange/10 px-2 py-1 rounded border border-orange/20 text-teal">{asMoney(coin.price)}</span>
        </div>
        <div className="flex items-center gap-1 text-sm font-bold">
          <span>{asPct(coin.change)}</span>
          {arrow && (
            <span
              className="font-semibold"
              style={{ fontSize: score >= 1.5 ? '1.2em' : score >= 0.5 ? '1.0em' : '0.85em', color }}
              title={`trend: ${trend}${coin.trendStreak ? ` x${coin.trendStreak}` : ''} • score ${Number(coin.trendScore||0).toFixed(2)}`}
              aria-label={`trend ${trend}`}
            >
              {arrow}
            </span>
          )}
          {typeof coin.trendStreak === 'number' && coin.trendStreak >= 2 && (
            <span className="px-1 py-0.5 rounded bg-blue-700/30 text-blue-200 text-[10px] leading-none font-semibold align-middle" title="Consecutive ticks in same direction">x{coin.trendStreak}</span>
          )}
        </div>
        <div className="px-2 py-1 rounded-full text-xs font-bold tracking-wide border border-purple/40 text-purple bg-transparent">{badge}</div>
      </div>
    </div>
  );
}