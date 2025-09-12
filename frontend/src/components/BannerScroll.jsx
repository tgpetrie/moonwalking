import React from 'react';

const BannerScroll = ({ items = [], tone = 'neutral' }) => {
  const getBadgeStyle = (change) => {
    const absChange = Math.abs(Number(change || 0));
    if (absChange >= 5) return 'STRONG HIGH';
    if (absChange >= 2) return 'STRONG';
    return '';
  };

  const formatPercentage = (value) => {
    const num = Number(value);
    return !isFinite(num) ? '0.00%' : `${num >= 0 ? '+' : ''}${num.toFixed(2)}%`;
  };

  const formatPrice = (value) => {
    const num = Number(value);
    return !isFinite(num) ? '0.00' : num.toFixed(4);
  };

  if (!items || items.length === 0) {
    return (
      <div className="overflow-hidden py-3 bg-black/20 border-t border-b border-gray-800">
        <div className="text-center text-gray-400 text-sm">
          No data available
        </div>
      </div>
    );
  }

  const toneClass = tone === 'gainer' ? 'text-green-400' : tone === 'loser' ? 'text-red-400' : 'text-gray-300';

  return (
    <div className="overflow-hidden py-3 bg-black/20 border-t border-b border-gray-800">
      <div className="flex animate-scroll whitespace-nowrap">
        {items.map((item, index) => (
          <div key={index} className="inline-flex items-center gap-2 px-6 text-sm">
            <span className="font-bold text-white">{item.symbol || item.name}</span>
            <span className={`font-mono ${toneClass}`}>
              ${formatPrice(item.price || item.current_price)}
            </span>
            <span className={`font-mono font-bold ${toneClass}`}>
              {formatPercentage(item.change || item.price_change_percentage_1hour)}
            </span>
            {getBadgeStyle(item.change || item.price_change_percentage_1hour) && (
              <span className="px-1 py-0.5 bg-purple-600 text-white text-xs rounded">
                {getBadgeStyle(item.change || item.price_change_percentage_1hour)}
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

export default BannerScroll;