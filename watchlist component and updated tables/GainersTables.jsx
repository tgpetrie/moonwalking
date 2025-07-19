
import React from 'react';

export default function GainersTable({ toggleWatch, watchlist, data }) {
  const dummyData = [
    { asset: 'SOL-USD', change_3m: 3.51, price: 42.78 },
    { asset: 'AVAX-USD', change_3m: 2.89, price: 15.32 },
  ];

  return (
    <div className="container mx-auto">
      {data.map((coin, idx) => (
        <div key={coin.asset} className="flex justify-between items-center border-b border-white/10 py-2">
          <div className="text-sm font-mono">{coin.asset}</div>
          {/* New Feature: Watchlist Toggle */}
          <div className="text-blue-400 text-sm font-mono">{coin.change_3m.toFixed(2)}%</div>
          <div className="text-sm text-gray-300">${coin.price.toFixed(2)}</div>
          <button onClick={() => toggleWatch(coin.asset)} className="ml-2 text-yellow-400">
            {watchlist.includes(coin.asset) ? "★" : "☆"}
          </button>
        </div>
      ))}
    </div>
  );
}
