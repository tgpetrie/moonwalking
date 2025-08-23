import React, { useEffect, useMemo, useRef, useState, useLayoutEffect } from 'react';
import { API_ENDPOINTS } from '../lib/api.js';
import Amount from './Amount.jsx';

const API_BASE = import.meta?.env?.VITE_API_URL || '';
const fetchJSON = async (path) => {
  const url = path?.startsWith('http') ? path : `${API_BASE}${path}`;
  const res = await fetch(url, { headers: { Accept: 'application/json' } });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export default function BottomBannerScroll({ pollMs = 15000, label = '1H Volume Change • Live Market Feed' }) {
  const [items, setItems] = useState([]);
  const envSlow = (import.meta?.env?.VITE_SLOW_BANNERS === 'true');
  const [slowMode, setSlowMode] = useState(() => {
    try {
      const v = localStorage.getItem('slowMarquee');
      if (v !== null) return v === '1' || v === 'true';
    } catch (e) {}
    return envSlow;
  });
  const [speedFactor, setSpeedFactor] = useState(() => {
    try { const s = localStorage.getItem('marqueeSpeedFactor'); return s ? Number(s) : 1.0; } catch (e) { return 1.0; }
  });
  const wrapRef = useRef(null);
  const trackRef = useRef(null);
  const [animKey, setAnimKey] = useState(0);
  const [durationSec, setDurationSec] = useState(60);

  const normalize = (raw = []) => {
    const arr = Array.isArray(raw) ? raw : raw?.data || raw?.items || raw?.headlines || [];
    if (!Array.isArray(arr)) return [];
    return arr.map((item, index) => {
      const volPct = Number.isFinite(item.volume_change_1h_pct)
        ? item.volume_change_1h_pct
        : (Number.isFinite(item.volume_change_estimate) ? item.volume_change_estimate : 0);
      return {
        id: item.id ?? item._id ?? index,
        rank: index + 1,
        symbol: (item.symbol || item.ticker || '').replace('-USD', '') || 'N/A',
        price: item.current_price ?? item.price ?? item.last ?? 0,
        volume_change: volPct,
        isEstimated: !Number.isFinite(item.volume_change_1h_pct) && Number.isFinite(item.volume_change_estimate),
        volume_24h: item.volume_24h ?? 0,
        badge: badgeFromVol(item.volume_24h ?? 0),
        trendDirection: item.trend_direction ?? item.trendDirection ?? 'flat',
        trendStreak: item.trend_streak ?? item.trendStreak ?? 0,
        trendScore: item.trend_score ?? item.trendScore ?? 0,
      };
    }).filter(x => x.symbol && x.symbol !== 'N/A');
  };

  const badgeFromVol = (v) => {
    if (v >= 10_000_000) return 'HIGH VOL';
    if (v >= 1_000_000) return 'MODERATE';
    if (v >= 100_000) return 'STRONG';
    return 'LOW VOL';
  };

  useEffect(() => {
    let alive = true; let timer;
    const run = async () => {
      try {
        const res = await fetchJSON(API_ENDPOINTS.bottomBanner);
        const next = normalize(res);
        if (alive && next.length) setItems(next.slice(0, 20));
        else if (alive && !items.length) setItems(fallbackItems());
      } catch (_) {
        if (alive && !items.length) setItems(fallbackItems());
      }
      timer = setTimeout(run, pollMs);
    };
    run();
    return () => { alive = false; clearTimeout(timer); };
  }, [pollMs]);

  const animDeps = useMemo(() => items.map(i=>i.id).join(','), [items]);
  useEffect(() => { setAnimKey(k=>k+1); }, [animDeps]);

  const ensureAtLeast = (arr, n) => {
    if (!Array.isArray(arr) || !arr.length) return [];
    const out = [...arr];
    for (let i = 0; out.length < n; i++) out.push(arr[i % arr.length]);
    return out.slice(0, n);
  };
  const viewItems = ensureAtLeast(items, 20);

  useLayoutEffect(() => {
    const calc = () => {
      const track = trackRef.current; const wrap = wrapRef.current;
      if (!track || !wrap) return;
      const total = track.scrollWidth;
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
    <div className="relative overflow-hidden rounded-3xl w-full max-w-full" role="region" aria-label={label} style={{ background: 'transparent' }}>
      {/* Header */}
      <div className="px-3 sm:px-6 py-3 sm:py-4">
        <div className="flex items-center gap-2 sm:gap-3">
          <h3 className="text-base font-headline font-bold tracking-wide uppercase" style={{ color: 'rgb(254, 164, 0)' }} tabIndex={0}>
            {label}
          </h3>
          <div className="ml-auto flex items-center gap-3">
            <label className="inline-flex items-center gap-2 text-xs select-none">
              <input
                type="checkbox"
                checked={slowMode}
                onChange={(e) => {
                  const v = e.target.checked;
                  setSlowMode(v);
                  try { localStorage.setItem('slowMarquee', v ? '1' : '0'); } catch (err) {}
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
      <div className="relative" style={{ position: 'relative', height: 64, overflow: 'hidden' }} ref={wrapRef} tabIndex={0} aria-label="Scrolling market data">
        {/* lighter edge fades to match table hover */}
        <div className="pointer-events-none absolute left-0 top-0 w-8 h-full" style={{background:'linear-gradient(to right, rgba(9,9,13,0.45), rgba(9,9,13,0.15), transparent)'}} />
        <div className="pointer-events-none absolute right-0 top-0 w-8 h-full" style={{background:'linear-gradient(to left, rgba(9,9,13,0.45), rgba(9,9,13,0.15), transparent)'}} />

        <div className="absolute inset-0 flex items-center" data-marquee>
          <div ref={trackRef} key={animKey} className="banner__track" style={{
            display: 'inline-flex',
            gap: '2rem',
            whiteSpace: 'nowrap',
            padding: '8px 12px',
            animation: `banner-scroll ${durationSec}s linear infinite`,
          }}>
            {/* First set */}
            {viewItems.map((coin) => (
              <BannerPill key={`a-${coin.id}`} coin={coin} />
            ))}
            {/* Duplicate for seamless loop */}
            {viewItems.map((coin) => (
              <BannerPill key={`b-${coin.id}`} coin={coin} />
            ))}
          </div>
        </div>
      </div>

      <style>{`
        @keyframes banner-scroll { from { transform: translateX(0); } to { transform: translateX(-50%); } }
        [data-marquee]:hover .banner__track { animation-play-state: paused; }
        .pill-hover, .banner-pill { background: transparent; }
        .pill-hover:hover, .banner-pill:hover { background: color-mix(in oklab, var(--panel, #0b0b0f) 70%, white 4%); }
      `}</style>
    </div>
  );
}

function BannerPill({ coin }) {
  const asMoney = (p) => {
    const n = Number(p) || 0; return `$${n < 1 ? n.toFixed(4) : n.toFixed(2)}`;
  };
  return (
    <div className="flex-shrink-0 mx-8 group" role="listitem" tabIndex={0} aria-label={`#${coin.rank} ${coin.symbol}, $${asMoney(coin.price).slice(1)}, Vol: ${coin.volume_change >= 0 ? '+' : ''}${Number(coin.volume_change||0).toFixed(2)}%, ${coin.badge}`}>
      <div className="flex items-center gap-4 banner-pill px-4 py-2 rounded-full transition-all duration-300 group-hover:text-purple group-hover:text-shadow-purple focus:ring-2 focus:ring-purple bg-transparent">
        <div className="flex items-center gap-2">
          <span className="text-xs font-bold text-purple">#{coin.rank}</span>
          <span className="text-sm font-headline font-bold tracking-wide">{coin.symbol}</span>
        </div>
        <div className="font-mono text-sm text-teal"><Amount value={Number(coin.price) || 0} /></div>
        <div className="flex items-center gap-1 text-sm font-bold">
          <span className={coin.volume_change >= 0 ? 'text-blue' : 'text-pink'}>
            Vol: <Amount value={Number(coin.volume_change||0)} type="percent" />
            {coin.isEstimated && (<sup title="Estimated from price when 1h volume history is incomplete">≈</sup>)}
          </span>
          {coin.trendDirection && coin.trendDirection !== 'flat' && (() => {
            const s = Math.max(0, Math.min(3, Number(coin.trendScore) || 0));
            let fontSize = '0.85em';
            if (s >= 1.5) fontSize = '1.2em'; else if (s >= 0.5) fontSize = '1.0em';
            const color = coin.trendDirection === 'up'
              ? (s >= 1.5 ? '#10B981' : s >= 0.5 ? '#34D399' : '#9AE6B4')
              : (s >= 1.5 ? '#EF4444' : s >= 0.5 ? '#F87171' : '#FEB2B2');
            return (
              <span className="font-semibold" style={{ fontSize, color }}
                title={`trend: ${coin.trendDirection}${coin.trendStreak ? ` x${coin.trendStreak}` : ''} • score ${Number(coin.trendScore||0).toFixed(2)}`}
                aria-label={`trend ${coin.trendDirection}`}
              >
                {coin.trendDirection === 'up' ? '↑' : '↓'}
              </span>
            );
          })()}
          {typeof coin.trendStreak === 'number' && coin.trendStreak >= 2 && (
            <span className="px-1 py-0.5 rounded bg-blue-700/30 text-blue-200 text-[10px] leading-none font-semibold align-middle" title="Consecutive ticks in same direction">x{coin.trendStreak}</span>
          )}
        </div>
        <div className="px-2 py-1 rounded-full text-xs font-bold tracking-wide border border-purple/40 bg-transparent">{coin.badge}</div>
      </div>
    </div>
  );
}

function fallbackItems() {
  return [
    { id: 'fb-1', rank: 1, symbol: 'SUKU', price: 0.0295, volume_change: 3.51, volume_24h: 25000000, badge: 'MODERATE' },
    { id: 'fb-2', rank: 2, symbol: 'HNT',  price: 2.30,   volume_change: 0.97, volume_24h: 18000000, badge: 'MODERATE' },
    { id: 'fb-3', rank: 3, symbol: 'OCEAN',price: 0.3162, volume_change: 0.60, volume_24h: 15000000, badge: 'MODERATE' },
    { id: 'fb-4', rank: 4, symbol: 'PENGU',price: 0.01605,volume_change: 0.56, volume_24h: 12000000, badge: 'MODERATE' },
    { id: 'fb-5', rank: 5, symbol: 'MUSE', price: 7.586,  volume_change: 0.53, volume_24h: 10000000, badge: 'MODERATE' },
  ];
}
