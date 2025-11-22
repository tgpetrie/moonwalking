// src/components/DashboardShell.jsx
import React, { useMemo, useState } from "react";
import TopBannerScroll from "./TopBannerScroll.jsx";
import TopBannerVolume1h from "./TopBannerVolume1h.jsx";
import GainersTable1Min from "./GainersTable1Min.jsx";
import GainersTable3Min from "./GainersTable3Min.jsx";
import Losers3m from "./Losers3m.jsx";
import WatchlistPanel from "./WatchlistPanel.jsx";
import InsightsPanel from "./InsightsPanel.jsx";
import { useWatchlist } from "../context/WatchlistContext.jsx";

export default function DashboardShell({ data, onInfo, onRefresh, rabbitLit }) {
  const [insightsSymbol, setInsightsSymbol] = useState(null);
  const {
    gainers1m = [],
    gainers3m = [],
    losers3m = [],
    banner1hPrice = [],
    banner1hVolume = [],
    meta = {},
    loading = false,
    error = null,
  } = data;
  const lastUpdated = meta?.last_updated;

  const handleInfo = (row) => {
    if (!row) return;
    const sym = (row.symbol || row.symbol?.toUpperCase() || row.ticker || row?.symbol)?.toString();
    setInsightsSymbol(sym);
  };

  const onInfoProp = onInfo || handleInfo;

  const gainers1mRows = useMemo(() => gainers1m || [], [gainers1m]);
  const { items: watchlistItems = [] } = useWatchlist();

  const handleRefreshClick = () => {
    if (typeof onRefresh === "function") {
      onRefresh();
    }
  };

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

      <div className="board-shell bh-board-shell">
        <div className="board-shell-inner">
          <section className="bh-banner-wrap bh-banner-wrap--top">
            <TopBannerScroll rows={banner1hPrice || []} loading={loading} error={error} onRefresh={onRefresh} />
            {/* keep legacy volume banner for shell symmetry; status gating inside component */}
          </section>

          <main className="bh-main">
            <div className="dashboard-shell">
              <div className="bh-board-inner">

                {/* ROW 1 – 1m gainers hero (full width) */}
                <section className="panel-row panel-row-1m">
                  <div className="panel-1m-slot">
                    <GainersTable1Min
                      rows={gainers1mRows}
                      loading={loading}
                      error={error}
                      onInfo={onInfoProp}
                    />
                  </div>
                </section>

                {/* ROW 2 – 3m gainers / losers pair aligned under same rails */}
                <section className="panel-row-3m">
                    <GainersTable3Min
                    rows={gainers3m || []}
                    loading={loading}
                    error={error}
                    onInfo={onInfoProp}
                  />
                  <Losers3m
                    rows={losers3m || []}
                    loading={loading}
                    error={error}
                    onInfo={onInfoProp}
                  />
                </section>

                {/* Ghost rabbit background placed after rows so it scrolls with the board */}
                <div className={`bh-rabbit-bg ${rabbitLit ? "is-lit" : ""}`} aria-hidden="true" />

                {/* ROW 3 – Watchlist (full width, centered under 3m pair) */}
                <section className="panel-row panel-row-watchlist">
                  <div className="panel-watchlist-slot">
                    <section className="panel panel-watchlist">
                      <WatchlistPanel title="WATCHLIST" onInfo={onInfoProp} />
                    </section>
                  </div>
                </section>

              </div>
            </div>
          </main>

          <section className="bh-banner-wrap bh-banner-wrap--bottom">
            <TopBannerVolume1h rows={banner1hVolume || []} />
          </section>
        </div>
      </div>

      {/* Insights floating card aligned to board-shell rails */}
      {insightsSymbol && (
        <div className="bh-insight-float">
          <InsightsPanel symbol={insightsSymbol} onClose={() => setInsightsSymbol(null)} />
        </div>
      )}
    </div>
  );
}
