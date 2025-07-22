import React, { useEffect, useState } from 'react';
import { API_ENDPOINTS, fetchData, getWatchlist, addToWatchlist, removeFromWatchlist } from '../api.js';
import { formatPrice, formatPercentage } from '../utils/formatters.js';
import StarIcon from './StarIcon';

const GainersTable = ({ refreshTrigger }) => {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [watchlist, setWatchlist] = useState([]);

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
        const response = await fetchData(API_ENDPOINTS.gainersTable);
        if (response && response.data && Array.isArray(response.data) && response.data.length > 0) {
          const gainersWithRanks = response.data.map((item, index) => ({
            rank: item.rank || (index + 1),
            symbol: item.symbol?.replace('-USD', '') || 'N/A',
            price: item.current_price || 0,
            change: item.price_change_percentage_3min || 0,
            badge: getBadgeText(Math.abs(item.price_change_percentage_3min || 0))
          }));
          if (isMounted) setData(gainersWithRanks.slice(0, 7));
        } else {
          if (isMounted) setData([]);
        }
        if (isMounted) setLoading(false);
      } catch (err) {
        console.error('Error fetching gainers data:', err);
        if (isMounted) {
          setLoading(false);
          setError(err.message);
          // Fallback mock data when backend offline
          const fallbackData = [
            { rank: 1, symbol: 'BTC-USD', current_price: 65000, price_change_percentage_3m: 5.23 },
            { rank: 2, symbol: 'ETH-USD', current_price: 3500, price_change_percentage_3m: 3.15 },
            { rank: 3, symbol: 'ADA-USD', current_price: 0.45, price_change_percentage_3m: 1.89 },
            { rank: 4, symbol: 'SOL-USD', current_price: 150, price_change_percentage_3m: 2.50 },
            { rank: 5, symbol: 'XRP-USD', current_price: 0.52, price_change_percentage_3m: 0.98 },
            { rank: 6, symbol: 'DOGE-USD', current_price: 0.15, price_change_percentage_3m: 1.20 },
            { rank: 7, symbol: 'LTC-USD', current_price: 70, price_change_percentage_3m: 0.75 }
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
    fetchGainersData();
    const interval = setInterval(fetchGainersData, 30000);
    return () => { isMounted = false; clearInterval(interval); };
  }, [refreshTrigger]);

  useEffect(() => {
    async function fetchWatchlist() {
      const data = await getWatchlist();
      setWatchlist(data);
    }
    fetchWatchlist();
  }, [refreshTrigger]);

  const handleToggleWatchlist = async (symbol) => {
    let updated;
    if (watchlist.includes(symbol)) {
      updated = await removeFromWatchlist(symbol);
    } else {
      updated = await addToWatchlist(symbol);
    }
    setWatchlist(updated);
  };

  if (loading && data.length === 0) {
    return (
      <div className="text-center py-8">
        <div className="animate-pulse text-blue font-mono">Loading gainers...</div>
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
        <div className="text-muted font-mono">No gainers data available</div>
      </div>
    );
  }

  return (
    <div className="flex flex-col space-y-2 sm:space-y-3 w-full h-full min-h-[420px] max-w-2xl mx-auto px-1 sm:px-3 md:px-0 align-stretch">
      {data.map((item, idx) => {
        const coinbaseUrl = `https://www.coinbase.com/advanced-trade/spot/${item.symbol.toLowerCase()}-USD`;
        const isInWatchlist = watchlist.includes(item.symbol);
        return (
          <React.Fragment key={item.symbol}>
            <div className="relative group flex-1 min-h-[56px]">
              <a
                href={coinbaseUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="block group flex-1 h-full"
              >
                <div
                  className="flex flex-row items-center justify-between p-4 rounded-xl transition-all duration-300 cursor-pointer relative overflow-hidden group-hover:text-purple group-hover:text-shadow-purple group-hover:scale-[1.025] group-hover:shadow-2xl group-hover:z-10 h-full min-h-[56px]"
                  style={{ boxShadow: '0 2px 16px 0 rgba(129,9,150,0.08)' }}
                >
                  {/* Diamond inner glow effect (hover only) */}
                  <span className="pointer-events-none absolute inset-0 flex items-center justify-center z-0">
                    <span
                      className="block w-[140%] h-[140%] rounded-xl opacity-0 group-hover:opacity-90 transition-opacity duration-1500"
                      style={{
                        background:
                          'radial-gradient(circle at 50% 50%, rgba(129,9,150,0.16) 0%, rgba(129,9,150,0.08) 60%, transparent 100%)',
                        top: '-20%',
                        left: '-20%',
                        position: 'absolute',
                      }}
                    />
                  </span>
                  <div className="flex items-center gap-5 w-[130px] min-w-[130px]">
                    {/* Rank Badge */}
                    <div className="flex items-center justify-center w-9 h-9 rounded-full text-blue font-extrabold text-base leading-none hover:text-purple hover:text-shadow-light-purple border border-blue/40" style={{aspectRatio:'1/1'}}>
                      {item.rank}
                    </div>
                    {/* Symbol */}
                    <div className="flex-1 flex items-center gap-3">
                      <span className="font-extrabold text-white text-xl leading-tight tracking-wide hover:text-purple hover:text-shadow-light-purple">
                        {item.symbol}
                      </span>
                    </div>
                  </div>
                  <div className="flex flex-row items-end gap-3 w-full sm:w-auto justify-end">
                    {/* Price Column (current and previous price, teal, right-aligned) */}
                    <div className="flex flex-col items-end min-w-[100px] leading-tight">
                      <span className="text-xl font-bold text-teal leading-tight">
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
                    <div className="flex flex-col items-end min-w-[90px]">
                      <div className={`flex items-center gap-1 font-bold text-lg ${item.change > 0 ? 'text-blue' : 'text-pink'}`}>
                        <span>{typeof item.change === 'number' ? formatPercentage(item.change) : 'N/A'}</span>
                      </div>
                      <span className="text-sm font-light text-gray-400">
                        3min change
                      </span>
                    </div>
                    <div className={`w-3 h-3 rounded-full ${getDotStyle(item.badge)}`}></div>
                    <StarIcon
                      filled={isInWatchlist}
                      onClick={e => { e.preventDefault(); handleToggleWatchlist(item.symbol); }}
                      className={isInWatchlist ? 'opacity-80 hover:opacity-100' : 'opacity-40 hover:opacity-80'}
                      style={{ minWidth: '20px', minHeight: '20px', cursor: 'pointer' }}
                    />
                  </div>
                </div>
              </a>
            </div>
            {/* Purple divider, not full width, only between cards */}
            {idx < data.length - 1 && (
              <div className="mx-auto my-0.5" style={{height:'2px',width:'60%',background:'linear-gradient(90deg,rgba(129,9,150,0.18) 0%,rgba(129,9,150,0.38) 50%,rgba(129,9,150,0.18) 100%)',borderRadius:'2px'}}></div>
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
};

export default GainersTable;