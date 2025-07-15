import React, { useEffect, useState } from 'react';
import { API_ENDPOINTS, fetchData } from '../api.js';
import { formatPrice, formatPercentage } from '../utils/formatters.js';

const LosersTable = ({ refreshTrigger }) => {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const getDotStyle = (badge) => {
    if (badge === 'STRONG HIGH') {
      return 'bg-red-400 shadow-lg shadow-red-400/50';
    } else if (badge === 'STRONG') {
      return 'bg-orange-400 shadow-lg shadow-orange-400/50';
    } else {
      return 'bg-yellow-400 shadow-lg shadow-yellow-400/50';
    }
  };

  const getBadgeText = (change) => {
    const absChange = Math.abs(change);
    if (absChange >= 5) return 'STRONG HIGH';
    if (absChange >= 2) return 'STRONG';
    return 'MODERATE';
  };

  useEffect(() => {
    let isMounted = true;
    const fetchLosersData = async () => {
      try {
        const response = await fetchData(API_ENDPOINTS.losersTable);
        if (response && response.data && Array.isArray(response.data) && response.data.length > 0) {
          const losersWithRanks = response.data.map((item, index) => ({
            rank: item.rank || (index + 1),
            symbol: item.symbol?.replace('-USD', '') || 'N/A',
            price: item.current_price || 0,
            change: item.price_change_percentage_3min || 0,
            badge: getBadgeText(Math.abs(item.price_change_percentage_3min || 0))
          }));
          if (isMounted) setData(losersWithRanks.slice(0, 7));
        } else if (isMounted && data.length === 0) {
          // Fallback data showing some crypto with negative/low gains
          setData([
            { rank: 1, symbol: 'PEPE', price: 0.00000996, change: -2.45, badge: 'MODERATE' },
            { rank: 2, symbol: 'SHIB', price: 0.00002156, change: -1.82, badge: 'MODERATE' },
            { rank: 3, symbol: 'FLOKI', price: 0.000234, change: -0.95, badge: 'MODERATE' },
            { rank: 4, symbol: 'BONK', price: 0.00001717, change: -0.67, badge: 'MODERATE' },
            { rank: 5, symbol: 'WIF', price: 2.543, change: -0.23, badge: 'MODERATE' },
            { rank: 6, symbol: 'NEW1', price: 1.234, change: -0.45, badge: 'MODERATE' },
            { rank: 7, symbol: 'NEW2', price: 0.567, change: -0.32, badge: 'MODERATE' }
          ]);
        }
        if (isMounted) setLoading(false);
      } catch (err) {
        console.error('Error fetching losers data:', err);
        if (isMounted) {
          setLoading(false);
          setError(err.message);
          
          // Fallback mock data when backend is offline
          const fallbackData = [
            { rank: 1, symbol: 'SEI-USD', current_price: 0.2244, price_change_percentage_3m: -12.89 },
            { rank: 2, symbol: 'AVAX-USD', current_price: 24.56, price_change_percentage_3m: -8.45 },
            { rank: 3, symbol: 'DOT-USD', current_price: 4.78, price_change_percentage_3m: -6.23 },
            { rank: 4, symbol: 'ATOM-USD', current_price: 7.89, price_change_percentage_3m: -9.34 },
            { rank: 5, symbol: 'NEAR-USD', current_price: 3.45, price_change_percentage_3m: -5.67 },
            { rank: 6, symbol: 'NEW1', current_price: 1.234, price_change_percentage_3m: -0.45 },
            { rank: 7, symbol: 'NEW2', current_price: 0.567, price_change_percentage_3m: -0.32 }
          ].map(item => ({
            ...item,
            price: item.current_price,
            change: item.price_change_percentage_3m,
            badge: getBadgeText(Math.abs(item.price_change_percentage_3m))
          }));
          setData(fallbackData);
        }
      }
    };
    fetchLosersData();
    const interval = setInterval(fetchLosersData, 30000);
    return () => { isMounted = false; clearInterval(interval); };
  }, [refreshTrigger]);

  if (loading && data.length === 0) {
    return (
      <div className="text-center py-8">
        <div className="animate-pulse text-pink font-mono">Loading losers...</div>
      </div>
    );
  }

  if (error && data.length === 0) {
    return (
      <div className="text-center py-8">
        <div className="text-muted font-mono">Backend offline - using demo data</div>
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <div className="text-center py-8">
        <div className="text-muted font-mono">No losers data available</div>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {data.map((item, idx) => {
        // Build Coinbase spot URL (symbol to lowercase)
        const coinbaseUrl = `https://www.coinbase.com/advanced-trade/spot/${item.symbol.toLowerCase()}-USD`;
        return (
          <React.Fragment key={item.symbol}>
            <a
              href={coinbaseUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="block group"
            >
              <div
                className="flex items-center justify-between p-4 rounded-xl transition-all duration-300 cursor-pointer relative overflow-hidden group-hover:text-purple group-hover:text-shadow-purple"
                style={{ position: 'relative' }}
              >
                {/* Subtle hot pink radial inner glow and hover effect */}
                <span className="pointer-events-none absolute inset-0 flex items-center justify-center z-0">
                  <span className="block w-[140%] h-[140%] rounded-xl opacity-0 group-hover:opacity-90 transition-opacity duration-1500" style={{background: 'radial-gradient(circle at 50% 50%, rgba(255,0,128,0.16) 0%, rgba(255,0,128,0.08) 60%, transparent 100%)', top: '-20%', left: '-20%', position: 'absolute'}} />
                </span>
                <div className="flex items-center gap-4">
                  {/* Rank Badge */}
                  <div className="flex items-center justify-center w-8 h-8 rounded-full bg-pink/20 text-pink font-bold text-sm hover:text-purple hover:text-shadow-light-purple">
                    {item.rank}
                  </div>
                  {/* Symbol */}
                  <div className="flex-1 flex items-center gap-3 ml-4">
                    <span className="font-bold text-white text-lg tracking-wide hover:text-purple hover:text-shadow-light-purple">
                      {item.symbol}
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  {/* Price Column (current and previous price, teal, right-aligned) */}
                  <div className="flex flex-col items-end min-w-[100px] ml-4">
                    <span className="text-lg font-bold text-teal">
                      {typeof item.price === 'number' && Number.isFinite(item.price)
                        ? formatPrice(item.price)
                        : 'N/A'}
                    </span>
                    <span className="text-sm font-light text-gray-400">
                      {typeof item.price === 'number' && typeof item.change === 'number' && item.change !== 0
                        ? (() => {
                             const prevPrice = item.price / (1 + item.change / 100);
                             return formatPrice(prevPrice);
                           })()
                        : '--'}
                    </span>
                  </div>
                  {/* Change Percentage and Dot */}
                  <div className="flex items-baseline gap-3 ml-4">
                    <div className="flex flex-col items-end">
                      <div className={`flex items-center gap-1 font-bold text-lg ${item.change > 0 ? 'text-blue-400' : 'text-pink'}`}>
                        <span>{typeof item.change === 'number' ? formatPercentage(item.change) : 'N/A'}</span>
                      </div>
                      <span className="text-sm font-light text-gray-400">
                        3min change
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className={`w-3 h-3 rounded-full ${getDotStyle(item.badge)}`}></div>
                    </div>
                  </div>
                </div>
              </div>
            </a>
            {/* Purple divider, not full width */}
            {idx < data.length - 1 && (
              <div className="mx-auto my-0.5" style={{height:'2px',width:'60%',background:'linear-gradient(90deg,rgba(129,9,150,0.18) 0%,rgba(129,9,150,0.38) 50%,rgba(129,9,150,0.18) 100%)',borderRadius:'2px'}}></div>
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}

export default LosersTable;
