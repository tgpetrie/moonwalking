import React from 'react';
import useSWR from 'swr';
import { API_ENDPOINTS, swrFetcher } from '../api.js';
import { useWebSocket } from '../context/websocketcontext.jsx';

const BottomBannerScroll = ({ refreshTrigger }) => {
  // Use SWR for data fetching with caching and periodic refresh
  const { data: response } = useSWR([API_ENDPOINTS.bottomBanner, refreshTrigger], swrFetcher, {
    refreshInterval: 60000,
    keepPreviousData: true
  });
  const { latestData } = useWebSocket() || {};
  // Prefer WS banner if available (provider sets crypto_meta.banner when backend sends structured payload)
  const wsBanner = Array.isArray(latestData?.crypto_meta?.banner) && latestData.crypto_meta.banner.length > 0
    ? latestData.crypto_meta.banner
    : null;

  const items = wsBanner || (Array.isArray(response?.data) && response.data.length > 0
    ? response.data
    : [
      { rank: 1, symbol: 'SUKU', price: 0.0295, volume_change: 3.51, volume_24h: 25000000, badge: 'MODERATE' },
      { rank: 2, symbol: 'HNT', price: 2.30, volume_change: 0.97, volume_24h: 18000000, badge: 'MODERATE' },
      { rank: 3, symbol: 'OCEAN', price: 0.3162, volume_change: 0.60, volume_24h: 15000000, badge: 'MODERATE' },
      { rank: 4, symbol: 'PENGU', price: 0.01605, volume_change: 0.56, volume_24h: 12000000, badge: 'MODERATE' },
    { rank: 5, symbol: 'MUSE', price: 7.586, volume_change: 0.53, volume_24h: 10000000, badge: 'MODERATE' }
    ]);
  // determine badge style based on 24h volume
  function getBadgeStyle(volume) {
    if (volume >= 10000000) return 'HIGH VOL';
    if (volume >= 1000000) return 'MODERATE';
    if (volume >= 100000) return 'STRONG';
    return 'LOW VOL';
  }
  const dataWithRanks = items.map((item, index) => ({
    rank: item.rank || index + 1,
    symbol: item.symbol.replace('-USD', '') || 'N/A',
    price: item.current_price ?? item.price ?? 0,
    volume_change: item.volume_change_1h_pct ?? item.volume_change ?? 0,
    isEstimated: item.volume_change_is_estimated ?? false,
    volume_24h: item.volume_24h ?? 0,
    badge: getBadgeStyle(item.volume_24h ?? 0),
    trendDirection: item.trend_direction ?? item.trendDirection ?? 'flat',
    trendStreak: item.trend_streak ?? item.trendStreak ?? 0,
    trendScore: item.trend_score ?? item.trendScore ?? 0
  }));
  const scrollData = dataWithRanks.slice(0, 20);


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
          <div className="flex whitespace-nowrap animate-scroll" role="list">
            {/* First set of data */}
            {scrollData.map((coin) => {
              const url = `https://www.coinbase.com/advanced-trade/spot/${coin.symbol.toLowerCase()}-usd`;
              return (
              <a
                key={`first-${coin.symbol}`}
                href={url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex-shrink-0 mx-8 group block"
                role="listitem"
                tabIndex={0}
                aria-label={`#${coin.rank} ${coin.symbol}, $${coin.price < 1 ? coin.price.toFixed(4) : coin.price.toFixed(2)}, Vol: ${coin.volume_change >= 0 ? '+' : ''}${coin.volume_change.toFixed(2)}%, ${coin.badge}`}
              >
                <div className="flex items-center gap-4 pill-hover px-4 py-2 rounded-full transition-all duration-300 group-hover:text-purple group-hover:text-shadow-purple focus:ring-2 focus:ring-purple bg-transparent">
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
                    <span className={coin.volume_change >= 0 ? 'text-blue' : 'text-pink'}>
                        Vol: {coin.volume_change >= 0 ? '+' : ''}{coin.volume_change.toFixed(2)}%
                        {coin.isEstimated && (
                          <sup title="Estimated from price when 1h volume history is incomplete">≈</sup>
                        )}
                    </span>
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
                  <div className="px-2 py-1 rounded-full text-xs font-bold tracking-wide border border-purple/40 bg-transparent">
                    {coin.badge}
                  </div>
                </div>
              </a>
              );
            })}
            {/* Duplicate set for seamless scrolling */}
            {scrollData.map((coin) => {
              const url = `https://www.coinbase.com/advanced-trade/spot/${coin.symbol.toLowerCase()}-usd`;
              return (
              <a
                key={`second-${coin.symbol}`}
                href={url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex-shrink-0 mx-8 group block"
                role="listitem"
                tabIndex={0}
                aria-label={`#${coin.rank} ${coin.symbol}, $${coin.price < 1 ? coin.price.toFixed(4) : coin.price.toFixed(2)}, Vol: ${coin.volume_change >= 0 ? '+' : ''}${coin.volume_change.toFixed(2)}%, ${coin.badge}`}
              >
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
                    <span className={coin.volume_change >= 0 ? 'text-blue' : 'text-pink'}>
                        Vol: {coin.volume_change >= 0 ? '+' : ''}{coin.volume_change.toFixed(2)}%
                        {coin.isEstimated && (
                          <sup title="Estimated from price when 1h volume history is incomplete">≈</sup>
                        )}
                    </span>
                    {coin.trendDirection && coin.trendDirection !== 'flat' && (() => {
                      const s = Math.max(0, Math.min(3, Number(coin.trendScore) || 0));
                      let fontSize = '0.85em';
                      if (s >= 1.5) fontSize = '1.2em'; else if (s >= 0.5) fontSize = '1.0em';
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
                    {typeof coin.trendStreak === 'number' && coin.trendStreak >= 2 && (
                      <span className="px-1 py-0.5 rounded bg-blue-700/30 text-blue-200 text-[10px] leading-none font-semibold align-middle" title="Consecutive ticks in same direction">x{coin.trendStreak}</span>
                    )}
                  </div>
                  <div className="px-2 py-1 rounded-full text-xs font-bold tracking-wide bg-purple/20 border border-purple/30">
                    {coin.badge}
                  </div>
                </div>
              </a>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};

export default BottomBannerScroll;
