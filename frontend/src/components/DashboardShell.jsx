// src/components/DashboardShell.jsx
import { useState } from "react";
import TopBannerScroll from "./TopBannerScroll.jsx";
import VolumeBannerScroll from "./VolumeBannerScroll.jsx";
import GainersTable1Min from "./GainersTable1Min.jsx";
import GainersTable3Min from "./GainersTable3Min.jsx";
import Losers3m from "./Losers3m.jsx";
import WatchlistPanel from "./WatchlistPanel.jsx";
import InsightsPanel from "./InsightsPanel.jsx";
import { useDataFeed } from "../hooks/useDataFeed";

export default function DashboardShell({ onInfo }) {
  const { data } = useDataFeed();
  const [insightsSymbol, setInsightsSymbol] = useState(null);
  const lastUpdated = data?.meta?.last_updated;

  const handleInfo = (symbol) => {
    const sym = symbol?.toString()?.toUpperCase();
    if (sym) setInsightsSymbol(sym);
  };

  const onInfoProp = onInfo || handleInfo;

  return (
    <div className="bh-app">
      <header className="bh-topbar">
        <div className="bh-logo">
          <span className="bh-logo-icon">🐇</span>
          <span className="bh-logo-text">BHABIT CB INSIGHT</span>
        </div>
        <div className="bh-topbar-right">
          {lastUpdated && (
            <span className="bh-topbar-meta">
              Latest: {new Date(lastUpdated).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
            </span>
          )}
        </div>
      </header>

      <main className="bh-main">
        <div className="bh-board">
          {/* Bunny layer behind 1m + 3m cluster */}
          <div className="bh-bunny-layer" aria-hidden="true">
            <img src="/nbg.png" alt="" aria-hidden="true" />
          </div>

          {/* 1h Price Banner (top) */}
          <section className="bh-board-row-full">
            <div className="bh-board-panel">
              <h2 className="bh-section-header">1h Price</h2>
              <TopBannerScroll />
            </div>
          </section>

          {/* 1-min Gainers (full-width or two-column, decided by component) */}
          <GainersTable1Min onInfo={onInfoProp} />

          {/* 3m Gainers / Losers (two-column) */}
          <section className="bh-board-row-halves">
            <GainersTable3Min onInfo={onInfoProp} />
            <Losers3m onInfo={onInfoProp} />
          </section>

          {/* Watchlist (full-width) */}
          <section className="bh-board-row-full bh-row-watchlist">
            <div className="bh-board-panel">
              <h2 className="bh-section-header">Watchlist</h2>
              <WatchlistPanel onInfo={onInfoProp} />
            </div>
          </section>

          {/* 1h Volume Banner (bottom) */}
          <section className="bh-board-row-full bh-row-volume">
            <div className="bh-board-panel">
              <h2 className="bh-section-header">1h Volume</h2>
              <VolumeBannerScroll />
            </div>
          </section>
        </div>
      </main>

      {/* Insights floating card aligned to board rails */}
      {insightsSymbol && (
        <div className="bh-insight-float">
          <InsightsPanel symbol={insightsSymbol} onClose={() => setInsightsSymbol(null)} />
        </div>
      )}
    </div>
  );
}
