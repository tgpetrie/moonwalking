import React, { useEffect, useState, useRef, useMemo } from 'react';
import { API_ENDPOINTS, fetchData } from '../api.js';

const TopBannerScroll = ({ refreshTrigger }) => {
  const [data, setData] = useState([]);
  // For seamless scroll across refreshes, hold a stable start timestamp
  const startRef = useRef(Date.now());
  const SCROLL_DURATION_SEC = 180; // matches .animate-scroll in index.css
  const animDelay = useMemo(() => {
    const elapsed = (Date.now() - startRef.current) / 1000;
    const offset = elapsed % SCROLL_DURATION_SEC;
    return `-${offset}s`;
  }, [data.length]);

  useEffect(() => {
    let isMounted = true;
    const fetchTopBannerData = async () => {
      try {
        const response = await fetchData(API_ENDPOINTS.topBanner);
        if (response && response.data && Array.isArray(response.data) && response.data.length > 0) {
          const dataWithRanks = response.data.map((item, index) => ({
            rank: index + 1,
            symbol: item.symbol?.replace('-USD', '') || 'N/A',
            price: item.current_price || 0,
            change: item.price_change_1h || 0,
            badge: getBadgeStyle(Math.abs(item.price_change_1h || 0)),
            trendDirection: item.trend_direction ?? item.trendDirection ?? 'flat',
            trendStreak: item.trend_streak ?? item.trendStreak ?? 0,
            trendScore: item.trend_score ?? item.trendScore ?? 0
          }));
          if (isMounted) {
            // Update data with real live data
            setData(dataWithRanks.slice(0, 20));
          }
        } else if (isMounted && data.length === 0) {
          // Only use fallback if we have no data at all
          const fallbackData = [
            { rank: 1, symbol: 'SUKU', price: 0.0295, change: 3.51, badge: 'STRONG' },
            { rank: 2, symbol: 'HNT', price: 2.30, change: 0.97, badge: '' },
            { rank: 3, symbol: 'OCEAN', price: 0.3162, change: 0.60, badge: '' },
            { rank: 4, symbol: 'PENGU', price: 0.01605, change: 0.56, badge: '' },
            { rank: 5, symbol: 'MUSE', price: 7.586, change: 0.53, badge: '' }
          ];
          setData(fallbackData);
        }
      } catch (err) {
        console.error('Error fetching top banner data:', err);
        if (isMounted && data.length === 0) {
          // Only use fallback on error if we have no existing data
          const fallbackData = [
            { rank: 1, symbol: 'SUKU', price: 0.0295, change: 3.51, badge: 'STRONG' },
            { rank: 2, symbol: 'HNT', price: 2.30, change: 0.97, badge: '' },
            { rank: 3, symbol: 'OCEAN', price: 0.3162, change: 0.60, badge: '' },
            { rank: 4, symbol: 'PENGU', price: 0.01605, change: 0.56, badge: '' },
            { rank: 5, symbol: 'MUSE', price: 7.586, change: 0.53, badge: '' }
          ];
          setData(fallbackData);
        }
      }
    };
    
    // Fetch data immediately
    fetchTopBannerData();
    return () => { isMounted = false; };
  }, [refreshTrigger]);

  const getBadgeStyle = (change) => {
    const absChange = Math.abs(change);
    if (absChange >= 5) return 'STRONG HIGH';
    if (absChange >= 2) return 'STRONG';
  return '';
  };

  // Never show loading or empty states - always render the banner
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
      <div className="relative h-16 overflow-hidden">
        {/* Left fade overlay */}
        <div className="absolute left-0 top-0 w-16 h-full bg-gradient-to-r from-black via-black/80 to-transparent z-10 pointer-events-none"></div>
        
        {/* Right fade overlay */}
        <div className="absolute right-0 top-0 w-16 h-full bg-gradient-to-l from-black via-black/80 to-transparent z-10 pointer-events-none"></div>
        
        <div className="absolute inset-0 flex items-center">
          <div 
              className="flex whitespace-nowrap animate-scroll"
              style={{ animationDelay: animDelay }}
              ref={(el)=>{
                if(!el) return;
                try{
                  const has = getComputedStyle(el).animationName;
                  if(!has || has === 'none'){
                    // Inject fallback keyframes once per element
                    if(!document.getElementById('fallback-scroll-keyframes')){
                      const s = document.createElement('style');
                      s.id = 'fallback-scroll-keyframes';
                      s.innerHTML = `@keyframes fallback-scroll { 0% { transform: translateX(0%);} 100% { transform: translateX(-100%);} } .fallback-animate-scroll { animation: fallback-scroll 180s linear infinite; }`;
                      document.head.appendChild(s);
                    }
                    el.classList.add('fallback-animate-scroll');
                  }
                }catch(e){/* ignore */}
              }}
            >
            {/* First set of data */}
            {data.map((coin) => (
              <div key={`first-${coin.symbol}`} className="flex-shrink-0 mx-8">
                <a href={`https://www.coinbase.com/advanced-trade/spot/${coin.symbol.toLowerCase()}-USD`} target="_blank" rel="noopener noreferrer"
                   className={"flex items-center gap-4 pill-hover px-4 py-2 rounded-full transition-all duration-300 group " +
                  (coin.change >= 0 ? 'group-hover:text-purple group-hover:text-shadow-purple' : 'group-hover:text-pink group-hover:text-shadow-pink')
                }>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold color-lock-purple">#{coin.rank}</span>
                    <span className="text-base font-headline font-bold tracking-wide">
                      {coin.symbol}
                    </span>
                    <span className="text-lg font-bold color-lock-teal">
                      ${coin.price < 1 ? coin.price.toFixed(4) : coin.price.toFixed(2)}
                    </span>
                  </div>
                  <div className="flex items-center gap-1 font-bold">
                    {(() => { const ch = Number(coin.change || 0); return (
                      <span className={(ch >= 0 ? 'color-lock-purple' : 'color-lock-pink') + ' text-xl'}>
                        {ch >= 0 ? '+' : ''}{Number.isFinite(ch) ? ch.toFixed(3) : '0.000'}%
                      </span>
                    ); })()}
                    {(() => { const ch = Number(coin.change || 0); if (!Number.isFinite(ch) || Math.abs(ch) < 0.01) return null; const color = ch >= 0 ? '#C026D3' : '#FF69B4'; const fontSize = Math.abs(ch) >= 2 ? '1.2em' : Math.abs(ch) >= 0.5 ? '1.0em' : '0.9em'; return (<span className="font-semibold" style={{ fontSize, color }} aria-label={ch >= 0 ? 'trend up' : 'trend down'}>{ch >= 0 ? '↑' : '↓'}</span>); })()}
                    {false && (() => {
                      const s = Math.max(0, Math.min(3, Number(coin.trendScore) || 0));
                      let fontSize = '0.85em';
                      if (s >= 1.5) fontSize = '1.2em'; else if (s >= 0.5) fontSize = '1.0em';
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
                    {/* streak chip removed for cleaner layout */}
                  </div>
                              {getBadgeStyle(coin.change) ? (
                                <div className="px-2 py-1 rounded-full text-xs font-bold tracking-wide bg-purple/20 border border-purple/30">
                                  {getBadgeStyle(coin.change)}
                                </div>
                              ) : null}
                </a>
              </div>
            ))}
            {/* Duplicate set for seamless scrolling */}
            {data.map((coin) => (
              <div key={`second-${coin.symbol}`} className="flex-shrink-0 mx-8">
                <a href={`https://www.coinbase.com/advanced-trade/spot/${coin.symbol.toLowerCase()}-USD`} target="_blank" rel="noopener noreferrer"
                   className={"flex items-center gap-4 pill-hover px-4 py-2 rounded-full transition-all duration-300 group " +
                  (coin.change >= 0 ? 'group-hover:text-purple group-hover:text-shadow-purple' : 'group-hover:text-pink group-hover:text-shadow-pink')
                }>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold color-lock-purple">#{coin.rank}</span>
                    <span className="text-base font-headline font-bold tracking-wide">
                      {coin.symbol}
                    </span>
                    <span className="text-lg font-bold color-lock-teal">
                      ${coin.price < 1 ? coin.price.toFixed(4) : coin.price.toFixed(2)}
                    </span>
                  </div>
                  <div className="flex items-center gap-1 font-bold">
                    {(() => { const ch = Number(coin.change || 0); return (
                      <span className={(ch >= 0 ? 'color-lock-purple' : 'color-lock-pink') + ' text-xl'}>
                        {ch >= 0 ? '+' : ''}{Number.isFinite(ch) ? ch.toFixed(3) : '0.000'}%
                      </span>
                    ); })()}
                    {(() => { const ch = Number(coin.change || 0); if (!Number.isFinite(ch) || Math.abs(ch) < 0.01) return null; const color = ch >= 0 ? '#C026D3' : '#FF69B4'; const fontSize = Math.abs(ch) >= 2 ? '1.2em' : Math.abs(ch) >= 0.5 ? '1.0em' : '0.9em'; return (<span className="font-semibold" style={{ fontSize, color }} aria-label={ch >= 0 ? 'trend up' : 'trend down'}>{ch >= 0 ? '↑' : '↓'}</span>); })()}
                    {false && (() => {
                      const s = Math.max(0, Math.min(3, Number(coin.trendScore) || 0));
                      let fontSize = '0.85em';
                      if (s >= 1.5) fontSize = '1.2em'; else if (s >= 0.5) fontSize = '1.0em';
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
                    {/* streak chip removed for cleaner layout */}
                  </div>
                              {getBadgeStyle(coin.change) ? (
                                <div className="px-2 py-1 rounded-full text-xs font-bold tracking-wide border border-purple/40 text-purple bg-transparent">
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
