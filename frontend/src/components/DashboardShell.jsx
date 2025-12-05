// src/components/DashboardShell.jsx
import React, { useMemo, useState } from "react";
import TopBannerScroll from "./TopBannerScroll.jsx";
import VolumeBannerScroll from "./VolumeBannerScroll.jsx";
import GainersTable1Min from "./GainersTable1Min.jsx";
import GainersTable3Min from "./GainersTable3Min.jsx";
import Losers3m from "./Losers3m.jsx";
import WatchlistPanel from "./WatchlistPanel.jsx";
import InsightsPanel from "./InsightsPanel.jsx";

export default function DashboardShell({ data, onInfo, bySymbol = {} }) {
  const [insightsSymbol, setInsightsSymbol] = useState(null);
  const {
    gainers1m = [],
    gainers3m = [],
    losers3m = [],
    banner1hPrice = [],
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

      <main className="dashboard-main">
        <div className="dashboard-shell board-shell bh-board-shell">
          <div className="bh-rabbit-bg" aria-hidden="true" />

          <section className="panel panel--banner panel--banner-top bh-banner-block bh-banner-block-top">
            <div className="section-head section-head--left section-head-gain">
              <span className="section-head__label">1H PRICE</span>
              <span className="section-head-line section-head-line-gain" />
            </div>
            <TopBannerScroll rows={banner1hPrice || []} loading={loading} error={error} />
          </section>

          <main className="bh-main">
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
            <section className="panel-row panel-row-3m">
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

            {/* ROW 3 – Watchlist (full width, centered under 3m pair) */}
            <section className="panel-row panel-row-watchlist">
              <div className="panel-watchlist-slot">
                <section className="panel panel-watchlist">
                  <WatchlistPanel title="WATCHLIST" onInfo={onInfoProp} bySymbol={bySymbol} />
                </section>
              </div>
            </section>
          </main>

          <section className="panel panel--banner panel--banner-bottom bh-banner-block bh-banner-block-bottom">
            <div className="section-head section-head--center section-head-loss">
              <span className="section-head__label">1H VOLUME</span>
              <span className="section-head-line section-head-line-loss" />
            </div>
            <VolumeBannerScroll />
          </section>
        </div>
      </main>

      {/* Insights floating card aligned to board-shell rails */}
      {insightsSymbol && (
        <div className="bh-insight-float">
          <InsightsPanel symbol={insightsSymbol} onClose={() => setInsightsSymbol(null)} />
        </div>
      )}
    </div>
  );
}
