// src/App.jsx
import React, { useState, useEffect } from "react";
import { WatchlistProvider, useWatchlist } from "./context/WatchlistContext.jsx";
import { useData } from "./hooks/useData.js";
import Gainers1m from "./components/Gainers1m.jsx";
import Gainers3m from "./components/Gainers3m.jsx";
import Losers3m from "./components/Losers3m.jsx";
import RefreshTicker from "./components/RefreshTicker.jsx";

// these are the real ones you said are in the repo
import InsightsTabbed from "./components/InsightsTabbed.jsx";
import AssetTabbedPanel from "./components/AssetTabbedPanel.jsx";

export default function App() {
  const { data, isLoading, mutate, bySymbol } = useData();
  const [selectedRow, setSelectedRow] = useState(null);

  const handleInfo = (payload) => {
    if (!payload) return;
    const sym = (payload.symbol || payload.ticker || "").replace("-USD", "");
    setSelectedRow({ ...payload, symbol: sym });
  };

  return (
    <WatchlistProvider>
      <WatchlistReconciler bySymbol={bySymbol} />
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
            <Gainers1m rows={data.gainers1m.rows} loading={data.gainers1m.loading} message={data.gainers1m.message} onInfo={handleInfo} />
            <Gainers3m rows={data.gainers3m.rows} loading={data.gainers3m.loading} message={data.gainers3m.message} onInfo={handleInfo} />
          </div>
          <div className="col col-right">
            <Losers3m rows={data.losers3m.rows} loading={data.losers3m.loading} message={data.losers3m.message} onInfo={handleInfo} />
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
function WatchlistReconciler({ bySymbol }) {
  const { refreshFromData } = useWatchlist();
  useEffect(() => {
    if (bySymbol && Object.keys(bySymbol).length) refreshFromData(bySymbol);
  }, [bySymbol, refreshFromData]);
  return null;
}
