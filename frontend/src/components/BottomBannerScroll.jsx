import React, { useEffect, useState, useRef, useMemo } from 'react';
import PropTypes from 'prop-types';
import { API_ENDPOINTS, fetchData } from '../api.js';

// Prefer an edge Worker URL when provided; fallback to backend route
const EDGE_URL = import.meta.env?.VITE_BOTTOM_BANNER_URL;
const FALLBACK_API = API_ENDPOINTS.bottomBanner;
const BANNER_API = EDGE_URL || FALLBACK_API;

const BottomBannerScroll = ({ refreshTrigger }) => {
  const [data, setData] = useState([]);
  const startRef = useRef(Date.now());
  const SCROLL_DURATION_SEC = 180; // keep in sync with CSS .animate-scroll
  const REFRESH_INTERVAL_MS = 120000; // 2-minute refresh cadence
  const animDelay = useMemo(() => {
    const elapsed = (Date.now() - startRef.current) / 1000;
    const offset = elapsed % SCROLL_DURATION_SEC;
    return `-${offset}s`;
  }, []);

  const marqueeRows = useMemo(() => {
    if (!data || data.length === 0) return [];
    const repeats = Math.max(2, Math.ceil(30 / data.length));
    const expanded = [];
    for (let r = 0; r < repeats; r += 1) {
      expanded.push(...data.map((coin, idx) => ({ ...coin, _marqueeId: `${coin.symbol}-${r}-${idx}` })));
    }
    return expanded;
  }, [data]);
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
        const raw = await (async () => {
          try {
            const res = await fetch(BANNER_API);
            if (res.ok) return await res.json();
          } catch (err) { console.warn('BottomBanner edge fetch failed, falling back', err); }
          return await fetchData(FALLBACK_API);
        })();
        const rows = Array.isArray(raw?.data)
          ? raw.data
          : Array.isArray(raw?.rows)
          ? raw.rows
          : [];
        if (rows && rows.length > 0) {
          const dataWithRanks = rows.map((item, index) => {
            const vol24 = Number(item.volume_24h ?? 0);
            let pctRaw = 0;
            const hasPct = (item.volume_change_1h_pct != null) && !Number.isNaN(Number(item.volume_change_1h_pct));
            const hasEst = (item.volume_change_estimate != null) && !Number.isNaN(Number(item.volume_change_estimate));
            if (hasPct) pctRaw = Number(item.volume_change_1h_pct);
            else if (hasEst) pctRaw = Number(item.volume_change_estimate);
            else pctRaw = Number(item.price_change_1h ?? 0) * 0.5;
            const isEst = !hasPct;
            return ({
              rank: index + 1,
              symbol: item.symbol?.replace('-USD', '') || 'N/A',
              price: Number(item.current_price ?? item.price ?? 0),
              volume_24h: vol24,
              volume_change: pctRaw,
              isEstimated: Boolean(item.volume_change_is_estimated ?? isEst),
              badge: getBadgeStyle(vol24),
              trendDirection: item.trend_direction ?? item.trendDirection ?? 'flat',
              trendStreak: item.trend_streak ?? item.trendStreak ?? 0,
              trendScore: item.trend_score ?? item.trendScore ?? 0
            });
          });
          if (isMounted) {
            setData(() => dataWithRanks.slice(0, 20));
          }
        } else if (isMounted) {
          const fallbackData = [
            { rank: 1, symbol: 'SUKU', price: 0.0295, volume_change: 3.51, volume_24h: 25000000, badge: 'MODERATE' },
            { rank: 2, symbol: 'HNT', price: 2.30, volume_change: 0.97, volume_24h: 18000000, badge: 'MODERATE' },
            { rank: 3, symbol: 'OCEAN', price: 0.3162, volume_change: 0.60, volume_24h: 15000000, badge: 'MODERATE' },
            { rank: 4, symbol: 'PENGU', price: 0.01605, volume_change: 0.56, volume_24h: 12000000, badge: 'MODERATE' },
            { rank: 5, symbol: 'MUSE', price: 7.586, volume_change: 0.53, volume_24h: 10000000, badge: 'MODERATE' }
          ];
          setData(prev => (prev.length ? prev : fallbackData));
        }
      } catch (err) {
        console.error('Error fetching bottom banner data:', err);
        if (isMounted) {
          const fallbackData = [
            { rank: 1, symbol: 'SUKU', price: 0.0295, volume_change: 3.51, volume_24h: 25000000, badge: 'MODERATE' },
            { rank: 2, symbol: 'HNT', price: 2.30, volume_change: 0.97, volume_24h: 18000000, badge: 'MODERATE' },
            { rank: 3, symbol: 'OCEAN', price: 0.3162, volume_change: 0.60, volume_24h: 15000000, badge: 'MODERATE' },
            { rank: 4, symbol: 'PENGU', price: 0.01605, volume_change: 0.56, volume_24h: 12000000, badge: 'MODERATE' },
            { rank: 5, symbol: 'MUSE', price: 7.586, volume_change: 0.53, volume_24h: 10000000, badge: 'MODERATE' }
          ];
          setData(prev => (prev.length ? prev : fallbackData));
        }
      }
    };
    // Fetch on mount, then refresh on a relaxed cadence
    const scheduleAtBoundary = () => {
      const elapsed = Date.now() - startRef.current;
      const msUntilRefresh = REFRESH_INTERVAL_MS - (elapsed % REFRESH_INTERVAL_MS);
      clearTimeout(timerId);
      timerId = setTimeout(async () => {
        await fetchBottomBannerData();
        scheduleAtBoundary();
      }, Math.max(250, msUntilRefresh));
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
    <section className="relative overflow-hidden rounded-3xl w-full max-w-full" aria-label="Live 1H Volume Change Market Feed" style={{ background: 'transparent' }}>
      {/* Header */}
      <div className="px-3 sm:px-6 py-3 sm:py-4">
        <div className="flex items-center gap-2 sm:gap-3">
          <h3 className="text-base font-headline font-bold tracking-wide uppercase text-orange" aria-label="1H Volume Change Live Market Feed">
            1H Volume Change • Live Market Feed
          </h3>
        </div>
      </div>
      {/* Scrolling Content */}
      <div className="relative h-16 overflow-hidden" aria-label="Scrolling market data" style={{outline:'none'}}>
        {/* Left fade overlay */}
        <div className="absolute left-0 top-0 w-16 h-full bg-gradient-to-r from-dark via-dark/80 to-transparent z-10 pointer-events-none"></div>
        {/* Right fade overlay */}
        <div className="absolute right-0 top-0 w-16 h-full bg-gradient-to-l from-dark via-dark/80 to-transparent z-10 pointer-events-none"></div>
        <div className="absolute inset-0 flex items-center">
          <ul className="flex whitespace-nowrap animate-scroll" style={{ animationDelay: animDelay }}>
            {/* First set of data */}
            {marqueeRows.map((coin, index) => (
              <li key={coin._marqueeId || `loop-${coin.symbol}-${index}`} className="flex-shrink-0 mx-8" aria-label={`${coin.symbol}, Vol $${formatAbbrev(coin.volume_24h)}, 1H ${coin.volume_change >= 0 ? '+' : ''}${Number(coin.volume_change||0).toFixed(3)}%`}>
                <a href={`https://www.coinbase.com/trade/${coin.symbol.toLowerCase()}-USD`} target="_blank" rel="noopener noreferrer" className="flex items-center gap-4 px-5 py-2 rounded-full transition-all duration-300 group hover:text-purple focus:ring-2 focus:ring-purple bg-black/20 border border-gray-800 hover:scale-105 will-change-transform">
                    <div className="flex items-center gap-2">
                    <span className="text-base font-headline font-bold tracking-wide">
                      {coin.symbol}
                    </span>
                  </div>
                  <div className="text-lg font-semibold text-teal" title={`24h volume: $${Number(coin.volume_24h||0).toLocaleString()}`}>
                    ${formatAbbrev(Number(coin.volume_24h||0))}
                  </div>
                  <div className="flex items-center gap-1 font-bold">
                    {(() => { const vc = Number(coin.volume_change || 0); return (
                      <span className={(vc >= 0 ? 'text-pos' : 'text-neg') + ' text-xl font-mono'}>
                        {vc >= 0 ? '+' : ''}{Number.isFinite(vc) ? vc.toFixed(3) : '0.000'}%
                      </span>
                    ); })()}
                    {/* directional arrow removed to avoid redundancy with +/- */}
                        {coin.isEstimated && (
                          <span className="text-xs ml-1 align-middle" title="Estimated from price when 1h volume history is incomplete">est</span>
                        )}
                    {/* trend arrows removed to avoid redundancy with +/- */}
                    {/* removed streak chip for cleaner layout */}
                  </div>
                  {/* removed empty purple-bordered pill for cleaner layout */}
                </a>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
};

export default BottomBannerScroll;

BottomBannerScroll.propTypes = {
  refreshTrigger: PropTypes.any,
};
