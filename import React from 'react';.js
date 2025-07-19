import React from 'react';

const CryptoRowSkeleton = () => (
  <div className="border-b border-gray-700/50 md:grid md:grid-cols-4 md:items-center md:gap-6 p-4 animate-pulse">
    {/* Column 1: Coin Info */}
    <div className="flex items-center gap-4 md:col-span-1">
      <div className="w-9 h-9 bg-gray-700 rounded-full"></div>
      <div>
        <div className="h-5 w-24 bg-gray-700 rounded mb-2"></div>
        <div className="h-4 w-12 bg-gray-700 rounded"></div>
      </div>
    </div>

    {/* Column 2: Price */}
    <div className="md:col-span-1 mt-4 md:mt-0">
      <div className="h-5 w-28 bg-gray-700 rounded"></div>
    </div>

    {/* Column 3: 24h Change */}
    <div className="hidden md:flex md:col-span-1">
      <div className="h-5 w-20 bg-gray-700 rounded"></div>
    </div>

    {/* Column 4: Market Cap */}
    <div className="md:col-span-1 mt-3 md:mt-0">
      <div className="h-5 w-32 bg-gray-700 rounded"></div>
    </div>
  </div>
);

export default CryptoRowSkeleton;