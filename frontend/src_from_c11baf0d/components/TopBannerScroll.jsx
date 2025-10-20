import React, { useEffect, useState, useRef, useMemo } from 'react';
import PropTypes from 'prop-types';
import { API_ENDPOINTS, fetchData } from '../api.js';

const TopBannerScroll = ({ refreshTrigger }) => {
  const [data, setData] = useState([]);
  const startRef = useRef(Date.now());
  const SCROLL_DURATION_SEC = 180; // matches .animate-scroll in index.css

  const getBadgeStyle = (change) => {
    const absChange = Math.abs(Number(change || 0));
    if (absChange >= 5) return 'STRONG HIGH';
    if (absChange >= 2) return 'STRONG';
    return '';
  };

  const animDelay = useMemo(() => {
    const elapsed = (Date.now() - startRef.current) / 1000;
    const offset = elapsed % SCROLL_DURATION_SEC;
    return `-${offset}s`;
  }, [data.length]);

  useEffect(() => {
    let isMounted = true;
    let timerId = null;

    const fetchTopBannerData = async () => {
      try {
        const response = await fetchData(API_ENDPOINTS.topBanner);
        const rows = Array.isArray(response?.data) ? response.data : [];

        if (rows.length > 0) {
          const dataWithRanks = rows.map((item, index) => {
            const pair = String(item.symbol || '');                 // e.g. "HBAR-USD"
            const base = pair.replace(/-USD$/i, '') || 'N/A';       // display
            const price = Number(item.current_price ?? 0);
            const change = Number(item.price_change_1h ?? 0);
            return {
              rank: index + 1,
              symbol: base,
              pair,            // keep full pair for link
              price,
              change,
              badge: getBadgeStyle(change),
            };
          });

          if (isMounted) setData(dataWithRanks.slice(0, 20));
        } else if (isMounted && data.length === 0) {
          // minimal, optional warm-up state (or keep your static fallback)
          setData([]);
        }
      } catch (err) {
        console.error('Error fetching top banner data:', err);
        if (isMounted && data.length === 0) {
          setData([]); // keep empty; UI still renders the frame
        }
      }
    };

    const scheduleAtBoundary = () => {
      const now = Date.now();
      const elapsed = now - startRef.current;
      const cycleMs = SCROLL_DURATION_SEC * 1000;
      const msUntilBoundary = cycleMs - (elapsed % cycleMs);
      clearTimeout(timerId);
      timerId = setTimeout(async () => {
        await fetchTopBannerData();
        scheduleAtBoundary();
      }, Math.max(250, msUntilBoundary));
    };

    fetchTopBannerData().then(() => scheduleAtBoundary());
    return () => { isMounted = false; clearTimeout(timerId); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshTrigger]);

  return (
    <div className="relative overflow-hidden rounded-3xl w-full max-w-full" style={{ background: 'transparent' }}>
      {/* Header */}
      <div className="px-3 sm:px-6 py-3 sm:py-4">
        <div className="flex items-center gap-2 sm:gap-3">
          <h3 className="text-base font-headline font-bold tracking-wide uppercase text-orange">
            1H Price Change • Live Market Feed
          </h3>
        </div>
      </div>

      {/* Scrolling Content */}
      <div className="relative h-16 overflow-hidden">
        <div className="absolute left-0 top-0 w-16 h-full bg-gradient-to-r from-dark via-dark/80 to-transparent z-10 pointer-events-none"></div>
        <div className="absolute right-0 top-0 w-16 h-full bg-gradient-to-l from-dark via-dark/80 to-transparent z-10 pointer-events-none"></div>

        <div className="absolute inset-0 flex items-center">
          <div className="flex whitespace-nowrap animate-scroll" style={{ animationDelay: animDelay }}>
            {data.map((coin) => (
              <div key={`first-${coin.symbol}`} className="flex-shrink-0 mx-8">
                <a
                  href={`https://www.coinbase.com/trade/${(coin.pair || (coin.symbol + '-USD')).toLowerCase()}`}
                  target="_blank" rel="noopener noreferrer"
                  className={
                    "flex items-center gap-4 px-5 py-2 rounded-full transition-all duration-300 group hover:scale-105 will-change-transform bg-black/20 border border-gray-800 " +
                    (coin.change >= 0 ? 'hover:text-purple hover:text-shadow-purple' : 'hover:text-pink hover:text-shadow-pink')
                  }
                >
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-pos">#{coin.rank}</span>
                    <span className="text-base font-headline font-bold tracking-wide">{coin.symbol}</span>
                    <span className="text-lg font-bold text-teal">
                      ${coin.price < 1 ? coin.price.toFixed(4) : coin.price.toFixed(2)}
                    </span>
                  </div>
                  <div className="flex items-center gap-1 font-bold">
                    {(() => {
                      const ch = Number(coin.change || 0);
                      const cls = ch >= 0 ? 'text-pos' : 'text-neg';
                      return (
                        <span className={`${cls} text-xl`}>
                          {ch >= 0 ? '+' : ''}{Number.isFinite(ch) ? ch.toFixed(3) : '0.000'}%
                        </span>
                      );
                    })()}
                    {(() => {
                      const ch = Number(coin.change || 0);
                      if (!Number.isFinite(ch) || Math.abs(ch) < 0.01) return null;
                      const color = ch >= 0 ? 'var(--pos)' : 'var(--neg)';
                      const mag = Math.abs(ch);
                      let fontSize = '0.9em';
                      if (mag >= 2) fontSize = '1.2em';
                      else if (mag >= 0.5) fontSize = '1.0em';
                      return <span className="font-semibold" style={{ fontSize, color }} aria-label={ch >= 0 ? 'trend up' : 'trend down'}>{ch >= 0 ? '↑' : '↓'}</span>;
                    })()}
                  </div>
                  {getBadgeStyle(coin.change) ? (
                    <div className="px-2 py-0.5 rounded-full text-xs font-bold tracking-wide bg-purple/20 border border-purple/40 text-purple">
                      {getBadgeStyle(coin.change)}
                    </div>
                  ) : null}
                </a>
              </div>
            ))}
            {/* Duplicate set for seamless scroll */}
            {data.map((coin) => (
              <div key={`second-${coin.symbol}`} className="flex-shrink-0 mx-8">
                <a
                  href={`https://www.coinbase.com/trade/${(coin.pair || (coin.symbol + '-USD')).toLowerCase()}`}
                  target="_blank" rel="noopener noreferrer"
                  className={
                    "flex items-center gap-4 px-5 py-2 rounded-full transition-all duration-300 group hover:scale-105 will-change-transform bg-black/20 border border-gray-800 " +
                    (coin.change >= 0 ? 'hover:text-purple hover:text-shadow-purple' : 'hover:text-pink hover:text-shadow-pink')
                  }
                >
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-pos">#{coin.rank}</span>
                    <span className="text-base font-headline font-bold tracking-wide">{coin.symbol}</span>
                    <span className="text-lg font-bold text-teal">
                      ${coin.price < 1 ? coin.price.toFixed(4) : coin.price.toFixed(2)}
                    </span>
                  </div>
                  <div className="flex items-center gap-1 font-bold">
                    {(() => {
                      const ch = Number(coin.change || 0);
                      const cls = ch >= 0 ? 'text-pos' : 'text-neg';
                      return (
                        <span className={`${cls} text-xl`}>
                          {ch >= 0 ? '+' : ''}{Number.isFinite(ch) ? ch.toFixed(3) : '0.000'}%
                        </span>
                      );
                    })()}
                    {(() => {
                      const ch = Number(coin.change || 0);
                      if (!Number.isFinite(ch) || Math.abs(ch) < 0.01) return null;
                      const color = ch >= 0 ? 'var(--pos)' : 'var(--neg)';
                      const mag = Math.abs(ch);
                      let fontSize = '0.9em';
                      if (mag >= 2) fontSize = '1.2em';
                      else if (mag >= 0.5) fontSize = '1.0em';
                      return <span className="font-semibold" style={{ fontSize, color }} aria-label={ch >= 0 ? 'trend up' : 'trend down'}>{ch >= 0 ? '↑' : '↓'}</span>;
                    })()}
                  </div>
                  {getBadgeStyle(coin.change) ? (
                    <div className="px-2 py-0.5 rounded-full text-xs font-bold tracking-wide border border-purple/40 text-purple bg-transparent">
                      {getBadgeStyle(coin.change)}
                    </div>
                  ) : null}
                </a>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default TopBannerScroll;

TopBannerScroll.propTypes = {
  refreshTrigger: PropTypes.any,
};
