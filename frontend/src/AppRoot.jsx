// src/AppRoot.jsx
import React, { useEffect, useState } from "react";
import { useData } from "./context/useData";
import { WatchlistProvider, useWatchlist } from "./context/WatchlistContext.jsx";
import TopBannerScroll from "./components/TopBannerScroll.jsx";
import TopBannerVolume1h from "./components/TopBannerVolume1h.jsx";
import GainersTable1Min from "./components/GainersTable1Min.jsx";
import GainersTable3Min from "./components/GainersTable3Min.jsx";
import LosersTable3Min from "./components/LosersTable3Min.jsx";
import WatchlistPanel from "./components/WatchlistPanel.jsx";
import InsightsTabbed from "./components/InsightsTabbed.jsx";
import AlertsIndicator from "./components/AlertsIndicator.jsx";
import AskBhabitPanel from "./components/AskBhabitPanel.jsx";

function WatchlistSync({ bySymbol }) {
  const { refreshFromData } = useWatchlist();
  useEffect(() => {
    if (!bySymbol) return;
    refreshFromData(bySymbol);
  }, [bySymbol, refreshFromData]);
  return null;
}

export default function AppRoot() {
  const {
    gainers1m,
    gainers3m,
    losers3m,
    top1hPrice,
    top1hVolume,
    meta,
    bySymbol,
    refresh,
    isLoading,
  } = useData();

  const [activeRow, setActiveRow] = useState(null);
  const [rabbitLit, setRabbitLit] = useState(false);

  const handleRefresh = async () => {
    await refresh();
    setRabbitLit(true);
    setTimeout(() => setRabbitLit(false), 280);
  };

  const handleInfo = (rowOrSymbol) => {
    if (!rowOrSymbol) return;
    setActiveRow(typeof rowOrSymbol === "string" ? { symbol: rowOrSymbol } : rowOrSymbol);
  };

  const handleRowHover = (symbol) => setRabbitLit(Boolean(symbol));

  return (
    <WatchlistProvider>
      <WatchlistSync bySymbol={bySymbol} />

      <div className="bh-app">
        <header className="bh-topbar">
          <div className="bh-topbar-left">
            <span className="bh-latest-pill">
              {meta?.last_updated
                ? `Latest: ${new Date(meta.last_updated).toLocaleTimeString()} on ${new Date(meta.last_updated).toLocaleDateString()}`
                : "Latest: --"}
            </span>
          </div>
          <div className="bh-topbar-right">
            <span className="bh-live-dot" />
            <button className="bh-refresh-btn" onClick={handleRefresh}>
              Refresh
            </button>
          </div>
        </header>

        <section className="bh-hero">
          <img src="/bhabit-logo.png" alt="BHABIT" className="bh-hero-logo" />
          <img src="/pbi.png" alt="Profits Buy Impulse" className="bh-hero-subtitle" />
        </section>

        <AlertsIndicator />

        <TopBannerScroll rows={top1hPrice?.rows || []} onRefresh={handleRefresh} />

        <main className="bh-main">
          {/* ROW 1 – 1-MIN GAINERS HERO (full-width) */}
          <section className="bh-row bh-row-1m">
            <GainersTable1Min
              packet={gainers1m}
              onInfo={handleInfo}
              onRowHover={handleRowHover}
            />
          </section>

          {/* ROW 2 – 3-MIN GAINERS / LOSERS + WATCHLIST */}
          <section className="bh-row bh-row-3m">
            <div className="bh-left-col">
              <GainersTable3Min
                packet={gainers3m}
                onInfo={handleInfo}
                onRowHover={handleRowHover}
              />
            </div>

            <div className="bh-right-col">
              <LosersTable3Min
                packet={losers3m}
                onInfo={handleInfo}
                onRowHover={handleRowHover}
              />
              <WatchlistPanel onInfo={handleInfo} />
            </div>
          </section>
        </main>

        <TopBannerVolume1h rows={top1hVolume?.rows || []} />

        <div className={`bh-rabbit-bg ${rabbitLit ? "is-lit" : ""}`} aria-hidden="true" />

        {activeRow && (
          <div className="bh-insight-float">
            <InsightsTabbed row={activeRow} onClose={() => setActiveRow(null)} />
          </div>
        )}
      </div>
    </WatchlistProvider>
  );
}
