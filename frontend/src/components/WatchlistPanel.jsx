import React from 'react';
import Watchlist from './Watchlist';

const WatchlistPanel = ({ onWatchlistChange, topWatchlist, ...rest }) => {
  return (
    <div className="w-full">
      <Watchlist initialSymbols={topWatchlist} />
    </div>
  );
};

export default WatchlistPanel;