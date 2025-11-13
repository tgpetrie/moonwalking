// src/AppRoot.jsx
import React from "react";
import { useData } from "./context/DataContext.jsx";
import { useWatchlist } from "./context/WatchlistContext.jsx";
import AlertsIndicator from "./components/AlertsIndicator.jsx";
import AskBhabitPanel from "./components/AskBhabitPanel.jsx";
import Gainers1m from "./components/Gainers1m.jsx";
import WatchlistPanel from "./components/WatchlistPanel.jsx";
import ThreeMinuteGainers from "./components/ThreeMinuteGainers.jsx";
import ThreeMinuteLosers from "./components/ThreeMinuteLosers.jsx";
import SentimentCard from "./components/SentimentCard.jsx";
import SentimentCardSymbol from "./components/cards/SentimentCard.jsx";
import TopBannerVolume1h from "./components/TopBannerVolume1h.jsx";

export default function AppRoot() {
  const { data, loading } = useData();
  const { refreshFromData } = useWatchlist();
  const [selectedSymbol, setSelectedSymbol] = React.useState(null);

  const payload = data?.data || {};
  const gainers1m = payload.gainers_1m || [];
  const gainers3m = payload.gainers_3m || [];
  const losers3m = payload.losers_3m || [];
  const banner1h = payload.banner_1h || [];

  // keep watchlist prices in sync
  React.useEffect(() => {
    const idx = {};
    [banner1h, gainers1m, gainers3m, losers3m].forEach((list) => {
      if (Array.isArray(list)) {
        list.forEach((t) => {
          if (t && t.symbol) idx[t.symbol] = t;
        });
      }
    });
    refreshFromData(idx);
  }, [banner1h, gainers1m, gainers3m, losers3m, refreshFromData]);

  return (
    <div className="bh-app">
      <header className="bh-topbar">
        <div className="bh-logo-mark">B</div>
        <div className="bh-top-title">
          <h1>BHABIT Crypto Dashboard</h1>
          <p>Live momentum · sentiment · signals</p>
        </div>
      </header>

  <AlertsIndicator />

      {/* NEW: 1h volume banner */}
      <TopBannerVolume1h items={banner1h} />

      <main className="bh-main">
        <div className="bh-row">
          <div className="bh-panel bh-panel-nopad" style={{ flex: 1.3 }}>
            <SentimentCard />
          </div>
          <div className="bh-panel bh-panel-nopad" style={{ flex: 0.7 }}>
            <AskBhabitPanel />
          </div>
        </div>

        <div className="bh-row bh-row-1m">
          <div className="bh-panel bh-panel-nopad">
            <Gainers1m rows={gainers1m} loading={loading} onInfo={setSelectedSymbol} />
          </div>
          <div className="bh-panel bh-panel-nopad">
            <WatchlistPanel />
          </div>
        </div>

        <div className="bh-row bh-row-3m">
          <div className="bh-panel bh-panel-nopad">
            <ThreeMinuteGainers rows={gainers3m} loading={loading} onInfo={setSelectedSymbol} />
          </div>
          <div className="bh-panel bh-panel-nopad">
            <ThreeMinuteLosers rows={losers3m} loading={loading} onInfo={setSelectedSymbol} />
          </div>
        </div>
      </main>

      {selectedSymbol && (
        <div className="bh-info-overlay" onClick={() => setSelectedSymbol(null)}>
          <div className="bh-info-panel" onClick={(e) => e.stopPropagation()}>
            <button className="bh-info-close" onClick={() => setSelectedSymbol(null)}>×</button>
            <h2>{selectedSymbol}</h2>
            <SentimentCardSymbol symbol={selectedSymbol} ttlSec={30} />
          </div>
        </div>
      )}
    </div>
  );
}
