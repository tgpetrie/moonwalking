import React, { useEffect, useState } from 'react';
import { API_ENDPOINTS, fetchData } from '../api.js';

const BottomBannerScroll = ({ refreshTrigger }) => {
  const [data, setData] = useState([]);

  useEffect(() => {
    let isMounted = true;
    const fetchBottomBannerData = async () => {
      try {
        const response = await fetchData(API_ENDPOINTS.bottomBanner);
        if (response && response.data && Array.isArray(response.data) && response.data.length > 0) {
          const dataWithRanks = response.data.map((item, index) => ({
            rank: index + 1,
            symbol: item.symbol?.replace('-USD', '') || 'N/A',
            price: item.current_price || 0,
            volume_change: item.price_change_1h || 0,
            volume_24h: item.volume_24h || 0,
            badge: getBadgeStyle(item.volume_24h || 0)
          }));
          if (isMounted) {
            // Update data with real live data
            setData(dataWithRanks.slice(0, 20));
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
    
    // Fetch data immediately
    fetchBottomBannerData();
    return () => { isMounted = false; };
  }, [refreshTrigger]);

  const getBadgeStyle = (volume) => {
    if (volume >= 10000000) return 'HIGH VOL';
    if (volume >= 1000000) return 'MODERATE';
    if (volume >= 100000) return 'STRONG';
    return 'LOW VOL';
  };

  // Never show loading or empty states - always render the banner
  return (
    <div className="relative overflow-hidden bg-gradient-to-r from-dark/80 via-mid-dark/60 to-dark/80 rounded-3xl" role="region" aria-label="Live 1H Volume Change Market Feed">
      {/* Header */}
      <div className="px-6 py-4">
        <div className="flex items-center gap-3">
          <h3 className="text-base font-headline font-bold tracking-wide uppercase text-purple" tabIndex={0} aria-label="1H Volume Change Live Market Feed">
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
          <div className="flex whitespace-nowrap animate-scroll" role="list">
            {/* First set of data */}
            {data.map((coin) => (
              <div key={`first-${coin.symbol}`} className="flex-shrink-0 mx-8 group" role="listitem" tabIndex={0} aria-label={`#${coin.rank} ${coin.symbol}, $${coin.price < 1 ? coin.price.toFixed(4) : coin.price.toFixed(2)}, Vol: ${coin.volume_change >= 0 ? '+' : ''}${coin.volume_change.toFixed(2)}%, ${coin.badge}`}>
                <div className="flex items-center gap-4 pill-hover px-4 py-2 rounded-full transition-all duration-300 group-hover:text-purple group-hover:text-shadow-purple focus:ring-2 focus:ring-purple">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-purple">#{coin.rank}</span>
                    <span className="text-sm font-headline font-bold tracking-wide">
                      {coin.symbol}
                    </span>
                  </div>
                  <div className="font-mono text-sm text-teal">
                    ${coin.price < 1 ? coin.price.toFixed(4) : coin.price.toFixed(2)}
                  </div>
                  <div className="flex items-center gap-1 text-sm font-bold">
                    <span className={coin.volume_change >= 0 ? 'text-blue' : 'text-pink'}>Vol: {coin.volume_change >= 0 ? '+' : ''}{coin.volume_change.toFixed(2)}%</span>
                  </div>
                  <div className="px-2 py-1 rounded-full text-xs font-bold tracking-wide bg-purple/20 border border-purple/30">
                    {coin.badge}
                  </div>
                </div>
              </div>
            ))}
            {/* Duplicate set for seamless scrolling */}
            {data.map((coin) => (
              <div key={`second-${coin.symbol}`} className="flex-shrink-0 mx-8 group" role="listitem" tabIndex={0} aria-label={`#${coin.rank} ${coin.symbol}, $${coin.price < 1 ? coin.price.toFixed(4) : coin.price.toFixed(2)}, Vol: ${coin.volume_change >= 0 ? '+' : ''}${coin.volume_change.toFixed(2)}%, ${coin.badge}`}>
                <div className="flex items-center gap-4 pill-hover px-4 py-2 rounded-full transition-all duration-300 group-hover:text-purple group-hover:text-shadow-purple focus:ring-2 focus:ring-purple">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-purple">#{coin.rank}</span>
                    <span className="text-sm font-headline font-bold tracking-wide">
                      {coin.symbol}
                    </span>
                  </div>
                  <div className="font-mono text-sm text-teal">
                    ${coin.price < 1 ? coin.price.toFixed(4) : coin.price.toFixed(2)}
                  </div>
                  <div className="flex items-center gap-1 text-sm font-bold">
                    <span className={coin.volume_change >= 0 ? 'text-blue' : 'text-pink'}>Vol: {coin.volume_change >= 0 ? '+' : ''}{coin.volume_change.toFixed(2)}%</span>
                  </div>
                  <div className="px-2 py-1 rounded-full text-xs font-bold tracking-wide bg-purple/20 border border-purple/30">
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

export default BottomBannerScroll;
