import React, { useEffect, useState } from 'react';
import { API_ENDPOINTS, fetchData } from '../api.js';

const TopBannerScroll = ({ refreshTrigger }) => {
  const [data, setData] = useState([]);

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
            { rank: 2, symbol: 'HNT', price: 2.30, change: 0.97, badge: 'MODERATE' },
            { rank: 3, symbol: 'OCEAN', price: 0.3162, change: 0.60, badge: 'MODERATE' },
            { rank: 4, symbol: 'PENGU', price: 0.01605, change: 0.56, badge: 'MODERATE' },
            { rank: 5, symbol: 'MUSE', price: 7.586, change: 0.53, badge: 'MODERATE' }
          ];
          setData(fallbackData);
        }
      } catch (err) {
        console.error('Error fetching top banner data:', err);
        if (isMounted && data.length === 0) {
          // Only use fallback on error if we have no existing data
          const fallbackData = [
            { rank: 1, symbol: 'SUKU', price: 0.0295, change: 3.51, badge: 'STRONG' },
            { rank: 2, symbol: 'HNT', price: 2.30, change: 0.97, badge: 'MODERATE' },
            { rank: 3, symbol: 'OCEAN', price: 0.3162, change: 0.60, badge: 'MODERATE' },
            { rank: 4, symbol: 'PENGU', price: 0.01605, change: 0.56, badge: 'MODERATE' },
            { rank: 5, symbol: 'MUSE', price: 7.586, change: 0.53, badge: 'MODERATE' }
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
    return 'MODERATE';
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
        <div className="absolute left-0 top-0 w-16 h-full bg-gradient-to-r from-dark via-dark/80 to-transparent z-10 pointer-events-none"></div>
        
        {/* Right fade overlay */}
        <div className="absolute right-0 top-0 w-16 h-full bg-gradient-to-l from-dark via-dark/80 to-transparent z-10 pointer-events-none"></div>
        
        <div className="absolute inset-0 flex items-center">
          <div 
            className="flex whitespace-nowrap animate-scroll"
          >
            {/* First set of data */}
            {data.map((coin) => (
              <div key={`first-${coin.symbol}`} className="flex-shrink-0 mx-8 group">
                <div className="flex items-center gap-4 pill-hover px-4 py-2 rounded-full transition-all duration-300 group-hover:text-purple group-hover:text-shadow-purple">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-purple">#{coin.rank}</span>
                    <span className="text-sm font-headline font-bold tracking-wide">
                      {coin.symbol}
                    </span>
                    <span className="font-mono text-base font-bold bg-orange/10 px-2 py-1 rounded border border-orange/20 text-teal">
                      ${coin.price < 1 ? coin.price.toFixed(4) : coin.price.toFixed(2)}
                    </span>
                  </div>
                  <div className="flex items-center gap-1 text-sm font-bold">
                    <span>{coin.change >= 0 ? '+' : ''}{coin.change.toFixed(2)}%</span>
                    {coin.trendDirection && coin.trendDirection !== 'flat' && (() => {
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
                    {typeof coin.trendStreak === 'number' && coin.trendStreak >= 2 && (
                      <span className="px-1 py-0.5 rounded bg-blue-700/30 text-blue-200 text-[10px] leading-none font-semibold align-middle" title="Consecutive ticks in same direction">x{coin.trendStreak}</span>
                    )}
                  </div>
                  <div className="px-2 py-1 rounded-full text-xs font-bold tracking-wide bg-purple/20 border border-purple/30">
                    {coin.badge}
                  </div>
                </div>
              </div>
            ))}
            {/* Duplicate set for seamless scrolling */}
            {data.map((coin) => (
              <div key={`second-${coin.symbol}`} className="flex-shrink-0 mx-8 group">
                <div className="flex items-center gap-4 pill-hover px-4 py-2 rounded-full transition-all duration-300 group-hover:text-purple group-hover:text-shadow-purple">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-purple">#{coin.rank}</span>
                    <span className="text-sm font-headline font-bold tracking-wide">
                      {coin.symbol}
                    </span>
                    <span className="font-mono text-base font-bold bg-orange/10 px-2 py-1 rounded text-teal">
                      ${coin.price < 1 ? coin.price.toFixed(4) : coin.price.toFixed(2)}
                    </span>
                  </div>
                  <div className="flex items-center gap-1 text-sm font-bold">
                    <span>{coin.change >= 0 ? '+' : ''}{coin.change.toFixed(2)}%</span>
                    {coin.trendDirection && coin.trendDirection !== 'flat' && (() => {
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
                    {typeof coin.trendStreak === 'number' && coin.trendStreak >= 2 && (
                      <span className="px-1 py-0.5 rounded bg-blue-700/30 text-blue-200 text-[10px] leading-none font-semibold align-middle" title="Consecutive ticks in same direction">x{coin.trendStreak}</span>
                    )}
                  </div>
                  <div className="px-2 py-1 rounded-full text-xs font-bold tracking-wide border border-purple/40 text-purple bg-transparent">
                    {coin.badge}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default TopBannerScroll;
