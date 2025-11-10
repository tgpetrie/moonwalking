// src/App.jsx
import React, { useState, useEffect } from "react";
import { WatchlistProvider, useWatchlist } from "./context/WatchlistContext.jsx";
import { useDashboardData } from "./hooks/useDashboardData.js";
import Gainers1m from "./components/Gainers1m.jsx";
import Gainers3m from "./components/Gainers3m.jsx";
import Losers3m from "./components/Losers3m.jsx";
import RefreshTicker from "./components/RefreshTicker.jsx";

// these are the real ones you said are in the repo
import InsightsTabbed from "./components/InsightsTabbed.jsx";
import AssetTabbedPanel from "./components/AssetTabbedPanel.jsx";

export default function App() {
  const { gainers1m, gainers3m, losers3m, priceMap, isLoading, mutate } = useDashboardData();
  const [selectedRow, setSelectedRow] = useState(null);

  const handleInfo = (payload) => {
    if (!payload) return;
    const sym = (payload.symbol || payload.ticker || "").replace("-USD", "");
    setSelectedRow({ ...payload, symbol: sym });
  };

  return (
    <WatchlistProvider>
      <WatchlistReconciler priceMap={priceMap} />
      <div className="bhabit-shell">
        <header className="topbar">
          <div className="topbar-left">
            <div className="logo-mark" />
            <div className="topbar-title">BHABITS CB INSIGHT</div>
          </div>
          <div className="topbar-right">
            <RefreshTicker onRefresh={mutate} />
          </div>
        </header>

        <main className="main-grid">
          <div className="col col-left">
            <Gainers1m rows={gainers1m} loading={isLoading} onInfo={handleInfo} />
            <Gainers3m rows={gainers3m} loading={isLoading} onInfo={handleInfo} />
          </div>
          <div className="col col-right">
            <Losers3m rows={losers3m} loading={isLoading} onInfo={handleInfo} />
          </div>
        </main>

        {selectedRow && (
          <div className="insight-floating">
            <InsightsTabbed row={selectedRow} />
          </div>
        )}
      </div>
    </WatchlistProvider>
  );
}

// keeps watchlist current price in sync with unified /api/data
function WatchlistReconciler({ priceMap }) {
  const { reconcilePrices } = useWatchlist();
  useEffect(() => {
    if (priceMap && Object.keys(priceMap).length) reconcilePrices(priceMap);
  }, [priceMap, reconcilePrices]);
  return null;
}
