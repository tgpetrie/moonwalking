// src/App.jsx
import React, { useEffect, useState } from "react";
import { WatchlistProvider, useWatchlist } from "./context/WatchlistContext.jsx";
import { useData } from "./hooks/useData.js";
import RefreshTicker from "./components/RefreshTicker.jsx";
import Gainers1m from "./components/Gainers1m.jsx";
import ThreeMinRow from "./components/ThreeMinRow.jsx";
import Losers3m from "./components/Losers3m.jsx";
import WatchlistPanel from "./components/WatchlistPanel.jsx";
import InsightsTabbed from "./components/InsightsTabbed.jsx";

function WatchlistReconciler({ bySymbol }) {
  const { refreshFromData } = useWatchlist();
  useEffect(() => {
    refreshFromData(bySymbol);
  }, [bySymbol, refreshFromData]);
  return null;
}

export default function App() {
  const { data, bySymbol, mutate } = useData();
  const [active, setActive] = useState(null);
  const [lit, setLit] = useState(false);

  const handleRefresh = async () => {
    try {
      await mutate();
    } finally {
      setLit(true);
      setTimeout(() => setLit(false), 300);
    }
  };

  const handleInfo = (rowOrSymbol) => {
    setActive(
      typeof rowOrSymbol === "string" ? { symbol: rowOrSymbol } : rowOrSymbol
    );
  };

  return (
    <WatchlistProvider>
      <WatchlistReconciler bySymbol={bySymbol} />
      <div className="bh-app">
        <header className="bh-topbar">
          <div className="bh-logo">
            <span className="bh-logo-icon">🐇</span>
            <span className="bh-logo-text">BHABIT CB INSIGHT</span>
          </div>
          <div className="bh-topbar-right">
            <RefreshTicker onRefresh={handleRefresh} />
          </div>
        </header>

        <div
          className={`bh-rabbit-bg ${lit ? "is-lit" : ""}`}
          aria-hidden="true"
        />

        <main className="bh-main">
          <div className="bh-left-col">
            <Gainers1m
              title="1-MINUTE GAINERS"
              rows={data.gainers1m.rows}
              loading={data.gainers1m.loading}
              onInfo={handleInfo}
            />
            <ThreeMinRow
              title="3-MINUTE GAINERS"
              rows={data.gainers3m.rows}
              onInfo={handleInfo}
            />
          </div>
          <div className="bh-right-col">
            <Losers3m
              title="3-MINUTE LOSERS"
              rows={data.losers3m.rows}
              onInfo={handleInfo}
            />
            <WatchlistPanel title="WATCHLIST" onInfo={handleInfo} />
          </div>
        </main>

        {active && (
          <div className="bh-insight-float">
            <InsightsTabbed row={active} />
          </div>
        )}
      </div>
    </WatchlistProvider>
  );
}
