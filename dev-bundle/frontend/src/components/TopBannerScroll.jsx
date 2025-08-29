import React, { useEffect, useMemo, useRef, useState, useLayoutEffect } from 'react';
import { API_ENDPOINTS } from '../lib/api.js';
import Amount from './Amount.jsx';

// Local fetch (decoupled from lib/api implementation details)
const API_BASE = import.meta?.env?.VITE_API_URL || '';
const fetchJSON = async (path) => {
  const url = path?.startsWith('http') ? path : `${API_BASE}${path}`;
  const res = await fetch(url, { headers: { Accept: 'application/json' } });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

// Polling + marquee with measured speed and hover-pause
export default function TopBannerScroll({ pollMs = 15000, fallbackLimit = 20 }) {
  const [items, setItems] = useState([]);
  // slowMode preference: localStorage override, fallback to Vite env var
  const envSlow = (import.meta?.env?.VITE_SLOW_BANNERS === 'true');
  const [slowMode, setSlowMode] = useState(() => {
    try {
      const v = localStorage.getItem('slowMarquee');
      if (v !== null) return v === '1' || v === 'true';
    } catch (e) {}
    return envSlow;
  });
  // speed factor slider (multiplies base pixels/sec). 1.0 = normal, <1 slower, >1 faster
  const [speedFactor, setSpeedFactor] = useState(() => {
    try { const s = localStorage.getItem('marqueeSpeedFactor'); return s ? Number(s) : 1.0; } catch (e) { return 1.0; }
  });
  const wrapRef = useRef(null);
  const trackRef = useRef(null);
  const [animKey, setAnimKey] = useState(0);
  const [durationSec, setDurationSec] = useState(60);

  // normalize API payload into a compact shape we render
  const normalize = (raw = []) => {
    const arr = Array.isArray(raw) ? raw : raw?.data || raw?.items || raw?.headlines || [];
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
        const res = await fetchJSON(API_ENDPOINTS.topBanner);
        const next = normalize(res);
        if (alive && next.length) setItems(next.slice(0, fallbackLimit));
        else if (alive && !items.length) setItems(fallbackItems());
      } catch (_) {
        if (alive && !items.length) setItems(fallbackItems());
      }
      timer = setTimeout(run, pollMs);
    };
    run();
    return () => { alive = false; clearTimeout(timer); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pollMs, fallbackLimit]);

  // Restart animation when list changes
  const animDeps = useMemo(() => items.map((i) => i.id).join(','), [items]);
  useEffect(() => { setAnimKey((k) => k + 1); }, [animDeps]);

  // Ensure we always have at least N items for a smooth loop
  const ensureAtLeast = (arr, n) => {
    if (!Array.isArray(arr) || !arr.length) return [];
    const out = [...arr];
    for (let i = 0; out.length < n; i++) out.push(arr[i % arr.length]);
    return out.slice(0, n);
  };
  const viewItems = ensureAtLeast(items, 20);

  // Measure width → set duration (slower + consistent)
  useLayoutEffect(() => {
    const calc = () => {
      const track = trackRef.current;
      const wrap = wrapRef.current;
      if (!track || !wrap) return;
      const total = track.scrollWidth; // duplicated content rendered below
      const visible = wrap.clientWidth || 1;
      // Slow the marquee: pixels/sec and min/max duration depend on slowMode
  const pixelsPerSecond = (slowMode ? 12 : 18) * (Number(speedFactor) || 1);
      const distance = Math.max(total * 0.5, visible);
      const secs = distance / pixelsPerSecond;
      const minSec = slowMode ? 140 : 80;
      const maxSec = slowMode ? 360 : 240;
      setDurationSec(Math.min(maxSec, Math.max(minSec, secs)));
    };
    const ro = new ResizeObserver(calc);
    if (wrapRef.current) ro.observe(wrapRef.current);
    if (trackRef.current) ro.observe(trackRef.current);
    window.addEventListener('resize', calc);
    calc();
    return () => { ro.disconnect(); window.removeEventListener('resize', calc); };
  }, [animKey, slowMode]);

  if (!viewItems.length) return null;

  return (
    <div className="relative overflow-hidden rounded-3xl w-full max-w-full" style={{ background: 'transparent' }}>
      {/* Header */}
      <div className="px-3 sm:px-6 py-3 sm:py-4">
        <div className="flex items-center gap-2 sm:gap-3">
          <h3 className="text-base font-headline font-bold tracking-wide uppercase" style={{ color: 'rgb(254, 164, 0)' }}>
            1H Price Change • Live Market Feed
          </h3>
          {/* Slow toggle (local preference); env VITE_SLOW_BANNERS can default this on */}
          <div className="ml-auto flex items-center gap-3">
            <label className="inline-flex items-center gap-2 text-xs select-none">
              <input
                type="checkbox"
                checked={slowMode}
                onChange={(e) => {
                  const v = e.target.checked;
                  setSlowMode(v);
                  try { localStorage.setItem('slowMarquee', v ? '1' : '0'); } catch (err) {}
                  // nudge animation recalculation
                  setAnimKey(k => k + 1);
                }}
              />
              <span>Slow</span>
            </label>

            <label className="inline-flex items-center gap-2 text-xs select-none">
              <span className="text-[11px] text-gray-300">Speed</span>
              <input
                aria-label="marquee speed"
                type="range"
                min="0.4"
                max="1.6"
                step="0.05"
                value={speedFactor}
                onChange={(e) => {
                  const v = Number(e.target.value) || 1;
                  setSpeedFactor(v);
                  try { localStorage.setItem('marqueeSpeedFactor', String(v)); } catch (err) {}
                  setAnimKey(k => k + 1);
                }}
              />
              <span className="text-[11px]">{Math.round((Number(speedFactor)||1) * 100)}%</span>
            </label>
          </div>
        </div>
      </div>

      {/* Scrolling Content */}
      <div className="relative" style={{ position: 'relative', height: 64, overflow: 'hidden' }} ref={wrapRef}>
        {/* lighter edge fades */}
        <div className="pointer-events-none absolute left-0 top-0 w-8 h-full" style={{background:'linear-gradient(to right, rgba(9,9,13,0.45), rgba(9,9,13,0.15), transparent)'}} />
        <div className="pointer-events-none absolute right-0 top-0 w-8 h-full" style={{background:'linear-gradient(to left, rgba(9,9,13,0.45), rgba(9,9,13,0.15), transparent)'}} />

        <div className="absolute inset-0 flex items-center" data-marquee>
          <div ref={trackRef} key={animKey} style={{
            display: 'inline-flex',
            gap: '2rem',
            whiteSpace: 'nowrap',
            padding: '8px 12px',
            animation: `banner-scroll ${durationSec}s linear infinite`,
            animationPlayState: 'running',
          }} className="banner__track">
            {/* First set */}
            {viewItems.map((coin) => (
              <Pill key={`a-${coin.id}`} coin={coin} badge={getBadge(coin.change)} />
            ))}
            {/* Duplicate for seamless loop */}
            {viewItems.map((coin) => (
              <Pill key={`b-${coin.id}`} coin={coin} badge={getBadge(coin.change)} />
            ))}
          </div>
        </div>
      </div>

      {/* Local keyframes + hover pause + subtle hover bg */}
      <style>{`
        @keyframes banner-scroll { from { transform: translateX(0); } to { transform: translateX(-50%); } }
        [data-marquee]:hover .banner__track { animation-play-state: paused; }
        .banner-pill { background: transparent; }
        .banner-pill:hover { background: color-mix(in oklab, var(--panel, #0b0b0f) 70%, white 4%); }
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
    const sign = n >= 0 ? '+' : '';
    const pct = Math.abs(n) <= 1 ? n : n; // already percent if >1
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
      <div className="flex items-center gap-4 banner-pill px-4 py-2 rounded-full transition-all duration-300 group-hover:text-purple group-hover:text-shadow-purple">
          <div className="flex items-center gap-2">
          <span className="text-xs font-bold text-purple">#{coin.rank}</span>
          <span className="text-sm font-headline font-bold tracking-wide">{coin.symbol}</span>
          <Amount value={Number(coin.price) || 0} className="font-mono text-base font-bold px-2 py-1 rounded text-teal" />
        </div>
          <div className="flex items-center gap-1 text-sm font-bold">
          <Amount value={Number(coin.change) || 0} type="percent" />
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

function fallbackItems() {
  return [
    { id: 'fb-1', rank: 1, symbol: 'SUKU', price: 0.0295, change: 3.51 },
    { id: 'fb-2', rank: 2, symbol: 'HNT',  price: 2.30,   change: 0.97 },
    { id: 'fb-3', rank: 3, symbol: 'OCEAN',price: 0.3162, change: 0.60 },
    { id: 'fb-4', rank: 4, symbol: 'PENGU',price: 0.01605,change: 0.56 },
    { id: 'fb-5', rank: 5, symbol: 'MUSE', price: 7.586,  change: 0.53 },
  ];
}
