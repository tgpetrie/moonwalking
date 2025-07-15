import React, { useEffect, useState } from 'react';
import { API_ENDPOINTS, fetchData } from '../api.js';
import { formatPrice, formatPercentage } from '../utils/formatters.js';

const GainersTable1Min = ({ refreshTrigger }) => {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isExpanded, setIsExpanded] = useState(false); // New state for expansion

  const getDotStyle = (badge) => {
    if (badge === 'STRONG HIGH') {
      return 'bg-green-400 shadow-lg shadow-green-400/50';
    } else if (badge === 'STRONG') {
      return 'bg-blue-400 shadow-lg shadow-blue-400/50';
    } else {
      return 'bg-teal-400 shadow-lg shadow-teal-400/50';
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
    const fetchGainersData = async () => {
      try {
const response = await fetchData(API_ENDPOINTS.gainersTable1Min);
        if (response && response.data && Array.isArray(response.data) && response.data.length > 0) {
          const gainersWithRanks = response.data.map((item, index) => ({
            rank: item.rank || (index + 1),
            symbol: item.symbol?.replace('-USD', '') || 'N/A',
            price: item.current_price || 0,
            change: item.price_change_percentage_1min || 0, // Use 1min change
            badge: getBadgeText(Math.abs(item.price_change_percentage_1min || 0))
          }));
          console.log("Raw API Response Data:", response.data); // Log raw data

          if (isMounted) {
            setData(gainersWithRanks.slice(0, 7)); // Set processed data
          }
        } else if (isMounted && data.length === 0) {
          // Fallback data showing some crypto with positive/high gains
          setData([
            { rank: 1, symbol: 'BTC', price: 65000, change: 5.23, badge: 'STRONG HIGH' },
            { rank: 2, symbol: 'ETH', price: 3500, change: 3.15, badge: 'STRONG' },
            { rank: 3, symbol: 'ADA', price: 0.45, change: 1.89, badge: 'MODERATE' },
            { rank: 4, symbol: 'SOL', price: 150, change: 2.50, badge: 'STRONG' },
            { rank: 5, symbol: 'XRP', price: 0.52, change: 0.98, badge: 'MODERATE' },
            { rank: 6, symbol: 'DOGE', price: 0.15, change: 1.20, badge: 'MODERATE' },
            { rank: 7, symbol: 'LTC', price: 70, change: 0.75, badge: 'MODERATE' }
          ]);
        }
        if (isMounted) setLoading(false);
      } catch (err) {
        console.error('Error fetching gainers data:', err);
        if (isMounted) {
          setLoading(false);
          setError(err.message);
          // Fallback mock data when backend offline
const fallbackData = [
            { rank: 1, symbol: 'BTC-USD', current_price: 65000, price_change_percentage_1min: 5.23 },
            { rank: 2, symbol: 'ETH-USD', current_price: 3500, price_change_percentage_1min: 3.15 },
            { rank: 3, symbol: 'ADA-USD', current_price: 0.45, price_change_percentage_1min: 1.89 },
            { rank: 4, symbol: 'SOL-USD', current_price: 150, price_change_percentage_1min: 2.50 },
            { rank: 5, symbol: 'XRP-USD', current_price: 0.52, price_change_percentage_1min: 0.98 },
            { rank: 6, symbol: 'DOGE-USD', current_price: 0.15, price_change_percentage_1min: 1.20 },
            { rank: 7, symbol: 'LTC-USD', current_price: 70, price_change_percentage_1min: 0.75 }
          ].map(item => ({
            ...item,
            price: item.current_price,
            change: item.price_change_percentage_1min,
            badge: getBadgeText(Math.abs(item.price_change_percentage_1min))
          }));
          setData(fallbackData);
        }
      }
    };
    fetchGainersData();
    const interval = setInterval(fetchGainersData, 30000); // Revert to 30 seconds
    return () => { isMounted = false; clearInterval(interval); };
  }, [refreshTrigger]);

  if (loading && data.length === 0) {
    return (
      <div className="text-center py-8">
        <div className="animate-pulse text-blue font-mono">Loading 1-min gainers...</div>
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
        <div className="text-muted font-mono">No 1-min gainers data available</div>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {data.slice(0, isExpanded ? data.length : 3).map((item, idx) => {
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
              >
                {/* Diamond inner glow effect (hover only) */}
                <span className="pointer-events-none absolute inset-0 flex items-center justify-center z-0">
                  <span
                    className="block w-[140%] h-[140%] rounded-xl opacity-0 group-hover:opacity-90 transition-opacity duration-1500"
                    style={{
                      background:
                        'radial-gradient(circle at 50% 50%, rgba(255,0,128,0.16) 0%, rgba(255,0,128,0.08) 60%, transparent 100%)',
                      top: '-20%',
                      left: '-20%',
                      position: 'absolute',
                    }}
                  />
                </span>
                <div className="flex items-center gap-4">
                  {/* Rank Badge */}
                  <div className="flex items-center justify-center w-8 h-8 rounded-full bg-blue/40 text-blue font-bold text-sm hover:text-purple hover:text-shadow-light-purple">
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
                        ? `$${item.price < 1 && item.price > 0 ? item.price.toFixed(4) : item.price.toFixed(2)}`
                        : 'N/A'}
                    </span>
                    <span className="text-sm font-light text-gray-400">
                      {typeof item.price === 'number' && typeof item.change === 'number' && item.change !== 0
                        ? (() => {
                             const prevPrice = item.price / (1 + item.change / 100);
                             return `$${prevPrice < 1 && prevPrice > 0 ? prevPrice.toFixed(4) : prevPrice.toFixed(2)}`;
                           })()
                        : '--'}
                    </span>
                  </div>
                  {/* Change Percentage and Dot */}
                  <div className="flex items-baseline gap-3 ml-4">
                    <div className="flex flex-col items-end">
                      <div className={`flex items-center gap-1 font-bold text-lg ${item.change > 0 ? 'text-blue' : 'text-pink'}`}>
                        <span>{typeof item.change === 'number' ? formatPercentage(item.change) : 'N/A'}</span>
                      </div>
                      <span className="text-sm font-light text-gray-400">
                        1min change
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className={`w-3 h-3 rounded-full ${getDotStyle(item.badge)}`}></div>
                    </div>
                  </div>
                </div>
              </div>
            </a>
            {/* Purple divider, not full width, only between cards */}
            {idx < data.slice(0, isExpanded ? data.length : 3).length - 1 && (
              <div className="mx-auto my-0.5" style={{height:'2px',width:'60%',background:'linear-gradient(90deg,rgba(129,9,150,0.18) 0%,rgba(129,9,150,0.38) 50%,rgba(129,9,150,0.18) 100%)',borderRadius:'2px'}}></div>
            )}
          </React.Fragment>
        );
      })}
      {data.length > 3 && (
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="w-1/3 py-2 text-blue font-bold rounded-xl bg-blue/10 hover:bg-blue/20 transition-colors duration-300 flex items-center justify-center gap-2 mx-auto"
        >
          {isExpanded ? (
            <>
              Show Less <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 transform rotate-180" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M14.707 12.707a1 1 0 01-1.414 0L10 9.414l-3.293 3.293a1 1 0 01-1.414-1.414l4-4a1 1 0 011.414 0l4 4a1 1 0 010 1.414z" clipRule="evenodd" /></svg>
            </>
          ) : (
            <>
              Show More <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clipRule="evenodd" /></svg>
            </>
          )}
        </button>
      )}
    </div>
  );
};

export default GainersTable1Min;