import React, { useEffect, useState, useRef, useMemo } from 'react';
import { API_ENDPOINTS } from '../api.js';
import { fetchJson } from '../lib/api.js';
import { formatPercent } from '../utils/formatters';
import formatSymbol from '../lib/format.js';
import { normalizeBannerRow } from '../lib/adapters';

// Prefer an edge Worker URL when provided; fallback to backend route
const EDGE_URL = import.meta.env?.VITE_BOTTOM_BANNER_URL;
const FALLBACK_API = API_ENDPOINTS.bottomBanner;
const BANNER_API = EDGE_URL || FALLBACK_API;

const BottomBannerScroll = ({ refreshTrigger }) => {
  const [data, setData] = useState([]);
  const startRef = useRef(Date.now());
  const SCROLL_DURATION_SEC = 180; // keep in sync with CSS .animate-scroll
  const animDelay = useMemo(() => {
    const elapsed = (Date.now() - startRef.current) / 1000;
    const offset = elapsed % SCROLL_DURATION_SEC;
    return `-${offset}s`;
  }, [data.length]);
  // Abbreviate large dollar amounts (e.g., 15,234,000 -> 15.23M)
  const formatAbbrev = (n = 0) => {
    const abs = Math.abs(n);
    const sign = n < 0 ? '-' : '';
    if (abs >= 1e12) return sign + (abs / 1e12).toFixed(2).replace(/\.0+$/,'') + 'T';
    if (abs >= 1e9)  return sign + (abs / 1e9).toFixed(2).replace(/\.0+$/,'') + 'B';
    if (abs >= 1e6)  return sign + (abs / 1e6).toFixed(2).replace(/\.0+$/,'') + 'M';
    if (abs >= 1e3)  return sign + (abs / 1e3).toFixed(1).replace(/\.0+$/,'') + 'k';
    return sign + String(abs.toFixed(0));
  };

  useEffect(() => {
    let isMounted = true;
    let timerId = null;
    const fetchBottomBannerData = async () => {
      try {
        // Use canonical fetchJson. Try EDGE url first, then fall back to backend route.
        const raw = await (async () => {
          try {
            const tryRes = await fetchJson(BANNER_API);
            if (tryRes) return tryRes;
          } catch (_e) {
            // ignore and fall back
          }
          return await fetchJson(FALLBACK_API);
        })();
        const rows = Array.isArray(raw?.rows) ? raw.rows
                  : (Array.isArray(raw?.data) ? raw.data : []);
        if (rows && rows.length > 0) {
          // normalize rows with adapter first
          const normalized = rows.map((r) => normalizeBannerRow(r));
          const dataWithRanks = normalized.map((item, index) => {
            const vol24 = Number(item.volume24h ?? 0) || Number(item.volume24h ?? 0);
            const pctRaw = item.volumeChangePct != null ? Number(item.volumeChangePct) : 0;
            return ({
              rank: index + 1,
              symbol: formatSymbol(item.symbol) || 'N/A',
              price: Number(item.currentPrice ?? 0),
              volume_24h: vol24,
              volume_change: pctRaw,
              isEstimated: Boolean(item.volumeChangeIsEstimated),
              badge: getBadgeStyle(vol24),
              trendDirection: item.trendDirection ?? item.trendDirection ?? 'flat',
              trendStreak: item.trendStreak ?? item.trendStreak ?? 0,
              trendScore: item.trendScore ?? item.trendScore ?? 0
            });
          });
          if (isMounted) {
            // Update data with real live data
            setData(dataWithRanks.slice(0, 20));
          }
          // dev: show a quick console snapshot when running Vite in dev
          try {
            if (import.meta.env.DEV && typeof console !== 'undefined') {
              // log summary: length and first item
              console.debug('[BottomBannerScroll] normalized data length', normalized.length, 'first:', normalized[0]);
            }
          } catch (e) {
            // ignore logging errors
          }
        } else if (isMounted && data.length === 0) {
          // Only use fallback if we have no data at all
          const fallbackData = [
            { rank: 1, symbol: 'SUKU', price: 0.0295, volume_change: 3.51, volume_24h: 25000000, badge: 'MODERATE' },
            { rank: 2, symbol: 'HNT', price: 2.30, volume_change: 0.97, volume_24h: 18000000, badge: 'MODERATE' },
            { rank: 3, symbol: 'OCEAN', price: 0.3162, volume_change: 0.60, volume_24h: 15000000, badge: 'MODERATE' },
            { rank: 4, symbol: 'PENGU', price: 0.01605, volume_change: 0.56, volume_24h: 12000000, badge: 'MODERATE' },
            { rank: 5, symbol: 'MUSE', price: 7.586, volume_change: 0.53, volume_24h: 10000000, badge: 'MODERATE' }
          ];
          setData(fallbackData);
        }
      } catch (err) {
        console.error('Error fetching bottom banner data:', err);
        if (isMounted && data.length === 0) {
          const fallbackData = [
            { rank: 1, symbol: 'SUKU', price: 0.0295, volume_change: 3.51, volume_24h: 25000000, badge: 'MODERATE' },
            { rank: 2, symbol: 'HNT', price: 2.30, volume_change: 0.97, volume_24h: 18000000, badge: 'MODERATE' },
            { rank: 3, symbol: 'OCEAN', price: 0.3162, volume_change: 0.60, volume_24h: 15000000, badge: 'MODERATE' },
            { rank: 4, symbol: 'PENGU', price: 0.01605, volume_change: 0.56, volume_24h: 12000000, badge: 'MODERATE' },
            { rank: 5, symbol: 'MUSE', price: 7.586, volume_change: 0.53, volume_24h: 10000000, badge: 'MODERATE' }
          ];
          setData(fallbackData);
        }
      }
    };
    // Fetch on mount, then refresh at end-of-scroll boundaries (hourly cap)
    const scheduleAtBoundary = () => {
      const now = Date.now();
      const elapsed = now - startRef.current;
      const cycleMs = SCROLL_DURATION_SEC * 1000;
      const msUntilBoundary = cycleMs - (elapsed % cycleMs);
      const cap = 60 * 60 * 1000; // 1 hour
      clearTimeout(timerId);
      timerId = setTimeout(async () => {
        await fetchBottomBannerData();
        scheduleAtBoundary();
      }, Math.min(Math.max(250, msUntilBoundary), cap));
    };

    fetchBottomBannerData().then(() => scheduleAtBoundary());
    return () => { isMounted = false; clearTimeout(timerId); };
  }, []);

  const getBadgeStyle = (volume) => {
  // Intentionally hide textual badge indicators in the bottom banner UI.
  // The visible pill remains for layout but we don't expose 'MODERATE'/'HIGH' labels.
  return '';
  };

  // Never show loading or empty states - always render the banner
  return (
    <div className="relative overflow-hidden rounded-3xl w-full max-w-full" role="region" aria-label="Live 1H Volume Change Market Feed" style={{ background: 'transparent' }}>
      {/* Header */}
      <div className="px-3 sm:px-6 py-3 sm:py-4">
        <div className="flex items-center gap-2 sm:gap-3">
          <h3 className="text-base font-headline font-bold tracking-wide uppercase" style={{ color: 'rgb(254, 164, 0)' }} tabIndex={0} aria-label="1H Volume Change Live Market Feed">
            1H Volume Change • Live Market Feed
          </h3>
        </div>
      </div>
      {/* Scrolling Content */}
      <div className="relative h-16 overflow-hidden" tabIndex={0} aria-label="Scrolling market data" style={{outline:'none'}}>
        {/* Left fade overlay */}
        <div className="absolute left-0 top-0 w-16 h-full bg-gradient-to-r from-dark via-dark/80 to-transparent z-10 pointer-events-none"></div>
        {/* Right fade overlay */}
        <div className="absolute right-0 top-0 w-16 h-full bg-gradient-to-l from-dark via-dark/80 to-transparent z-10 pointer-events-none"></div>
        <div className="absolute inset-0 flex items-center">
          <div className="flex whitespace-nowrap animate-scroll" role="list" style={{ animationDelay: animDelay }}>
            {/* First set of data */}
            {data.map((coin) => (
              <div key={`first-${coin.symbol}`} className="flex-shrink-0 mx-8" role="listitem" tabIndex={0} aria-label={`${coin.symbol}, Vol $${formatAbbrev(coin.volume_24h)}, 1H ${coin.volume_change >= 0 ? '+' : ''}${Number(coin.volume_change||0).toFixed(3)}%`}>
                <a href={`https://www.coinbase.com/advanced-trade/spot/${(coin.symbol||'').toLowerCase()}-USD`} target="_blank" rel="noopener noreferrer" className="flex items-center gap-4 pill-hover px-4 py-2 rounded-full transition-all duration-300 group hover:text-purple focus:ring-2 focus:ring-purple bg-transparent">
                    <div className="flex items-center gap-2">
                    <span className="text-base font-headline font-bold tracking-wide">
                      {formatSymbol(coin.symbol) || coin.symbol}
                    </span>
                  </div>
                  <div className="text-lg font-semibold text-teal" title={`24h volume: $${Number(coin.volume_24h||0).toLocaleString()}`}>
                    ${formatAbbrev(Number(coin.volume_24h||0))}
                  </div>
                  <div className="flex items-center gap-1 font-bold">
                    {(() => { const vc = Number(coin.volume_change || 0); return (
                      <span className={(vc >= 0 ? 'text-purple' : 'text-pink') + ' text-xl'}>
                        Vol: {formatPercent(vc, { fromFraction: false, max: 3, sign: true })}
                      </span>
                    ); })()}
                    {(() => { const vc = Number(coin.volume_change || 0); if (!Number.isFinite(vc) || Math.abs(vc) < 0.01) return null; const color = vc >= 0 ? '#C026D3' : '#FF69B4'; const fontSize = Math.abs(vc) >= 2 ? '1.2em' : Math.abs(vc) >= 0.5 ? '1.0em' : '0.9em'; return (<span className="font-semibold" style={{ fontSize, color }} aria-label={vc >= 0 ? 'trend up' : 'trend down'}>{vc >= 0 ? '↑' : '↓'}</span>); })()}
                        {coin.isEstimated && (
                          <sup title="Estimated from price when 1h volume history is incomplete">≈</sup>
                        )}
                    {coin.trendDirection && coin.trendDirection !== 'flat' && (() => {
                      const s = Math.max(0, Math.min(3, Number(coin.trendScore) || 0));
                      let fontSize = '0.85em';
                      if (s >= 1.5) { fontSize = '1.2em'; }
                      else if (s >= 0.5) { fontSize = '1.0em'; }
                      const color = coin.trendDirection === 'up'
                        ? (s >= 1.5 ? '#10B981' : s >= 0.5 ? '#34D399' : '#9AE6B4')
                        : (s >= 1.5 ? '#EF4444' : s >= 0.5 ? '#F87171' : '#FEB2B2');
                      return (
                        <span
                          className="font-semibold"
                          style={{ fontSize, color }}
                          title={`trend: ${coin.trendDirection}${coin.trendStreak ? ` x${coin.trendStreak}` : ''} • score ${Number(coin.trendScore||0).toFixed(2)}`}
                          aria-label={`trend ${coin.trendDirection}`}
                        >
                          {coin.trendDirection === 'up' ? '↑' : '↓'}
                        </span>
                      );
                    })()}
                    {/* removed streak chip for cleaner layout */}
                  </div>
                  {/* removed empty purple-bordered pill for cleaner layout */}
                </a>
              </div>
            ))}
            {/* Duplicate set for seamless scrolling */}
            {data.map((coin) => (
              <div key={`second-${coin.symbol}`} className="flex-shrink-0 mx-8" role="listitem" tabIndex={0} aria-label={`${coin.symbol}, Vol $${formatAbbrev(coin.volume_24h)}, 1H ${coin.volume_change >= 0 ? '+' : ''}${Number(coin.volume_change||0).toFixed(3)}%`}>
                <a href={`https://www.coinbase.com/advanced-trade/spot/${(coin.symbol||'').toLowerCase()}-USD`} target="_blank" rel="noopener noreferrer" className="flex items-center gap-4 pill-hover px-4 py-2 rounded-full transition-all duration-300 group hover:text-purple focus:ring-2 focus:ring-purple">
                  <div className="flex items-center gap-2">
                    <span className="text-base font-headline font-bold tracking-wide">
                      {formatSymbol(coin.symbol) || coin.symbol}
                    </span>
                  </div>
                  <div className="text-lg font-semibold text-teal" title={`24h volume: $${coin.volume_24h.toLocaleString()}`}>
                    ${formatAbbrev(coin.volume_24h)}
                  </div>
                  <div className="flex items-center gap-1 font-bold">
                    {(() => { const vc = Number(coin.volume_change || 0); return (
                      <span className={(vc >= 0 ? 'text-purple' : 'text-pink') + ' text-xl'}>
                        Vol: {formatPercent(vc, { fromFraction: false, max: 3, sign: true })}
                      </span>
                    ); })()}
                    {(() => { const vc = Number(coin.volume_change || 0); if (!Number.isFinite(vc) || Math.abs(vc) < 0.01) return null; const color = vc >= 0 ? '#C026D3' : '#FF69B4'; const fontSize = Math.abs(vc) >= 2 ? '1.2em' : Math.abs(vc) >= 0.5 ? '1.0em' : '0.9em'; return (<span className="font-semibold" style={{ fontSize, color }} aria-label={vc >= 0 ? 'trend up' : 'trend down'}>{vc >= 0 ? '↑' : '↓'}</span>); })()}
                        {coin.isEstimated && (
                          <sup title="Estimated from price when 1h volume history is incomplete">≈</sup>
                        )}
                    {coin.trendDirection && coin.trendDirection !== 'flat' && (() => {
                      const s = Math.max(0, Math.min(3, Number(coin.trendScore) || 0));
                      let fontSize = '0.85em';
                      if (s >= 1.5) { fontSize = '1.2em'; }
                      else if (s >= 0.5) { fontSize = '1.0em'; }
                      const color = coin.trendDirection === 'up'
                        ? (s >= 1.5 ? '#10B981' : s >= 0.5 ? '#34D399' : '#9AE6B4')
                        : (s >= 1.5 ? '#EF4444' : '#F87171');
                      return (
                        <span
                          className="font-semibold"
                          style={{ fontSize, color }}
                          title={`trend: ${coin.trendDirection}${coin.trendStreak ? ` x${coin.trendStreak}` : ''} • score ${Number(coin.trendScore||0).toFixed(2)}`}
                          aria-label={`trend ${coin.trendDirection}`}
                        >
                          {coin.trendDirection === 'up' ? '↑' : '↓'}
                        </span>
                      );
                    })()}
                    {/* removed streak chip for cleaner layout */}
                  </div>
                    {/* removed extra purple-bordered container - keep single layout pill in first set only */}
                </a>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default BottomBannerScroll;
