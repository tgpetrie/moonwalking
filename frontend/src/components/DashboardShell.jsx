// src/components/DashboardShell.jsx
import React from "react";
import RefreshTicker from "./RefreshTicker.jsx";
import TopBannerScroll from "./TopBannerScroll.jsx";
import TopBannerVolume1h from "./TopBannerVolume1h.jsx";
import MoversPanel from "./MoversPanel.jsx";
import WatchlistPanel from "./WatchlistPanel.jsx";

export default function DashboardShell({ data, onInfo, onRefresh, rabbitLit }) {
  const { gainers1m, gainers3m, losers3m, top1hPrice, top1hVolume, meta } = data;
  const lastUpdated = meta?.last_updated;

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
              Latest: {new Date(lastUpdated).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })} on {new Date(lastUpdated).toLocaleDateString([], { month: "short", day: "2-digit" })}
            </span>
          )}
          <RefreshTicker onRefresh={onRefresh} />
        </div>
      </header>
      <div className={`bh-rabbit-bg ${rabbitLit ? "is-lit" : ""}`} aria-hidden="true" />

      <section className="bh-banner-wrap">
        <TopBannerScroll rows={top1hPrice?.rows || []} onRefresh={onRefresh} />
      </section>

      <main className="bh-main">
        {/* Outer unified shell: both 1m and 3m rows live on the same horizontal rails */}
        <div className="mw-page-shell">
          {/* 1-minute pair row (left / right) — split into two separate panel cards so columns align with 3m below */}
          <section className="mw-pair-row mw-row-1m">
            <div className="mw-panel-card">
              <MoversPanel title="1-MIN GAINERS" variant="1m-left" packet={gainers1m} onInfo={onInfo} />
            </div>
            <div className="mw-panel-card">
              <MoversPanel title="1-MIN GAINERS" variant="1m-right" packet={gainers1m} onInfo={onInfo} />
            </div>
          </section>

          {/* 3-minute pair row (gainers / losers) */}
          <section className="mw-pair-row mw-row-3m">
            <div className="mw-panel-card">
              <MoversPanel title="3-MIN GAINERS" variant="3m-list" packet={gainers3m} onInfo={onInfo} />
            </div>
            <div className="mw-panel-card">
              <MoversPanel title="3-MIN LOSERS" variant="3m-list" packet={losers3m} onInfo={onInfo} forceDown />
            </div>
          </section>

          {/* Watchlist spans both columns */}
          <section className="mw-watchlist-row" aria-label="Watchlist Row">
            <div className="panel bh-watchlist-panel mw-panel-card">
              <WatchlistPanel title="WATCHLIST" onInfo={onInfo} />
            </div>
          </section>
        </div>
      </main>

      <section className="bh-banner-wrap bh-banner-wrap--bottom">
        <TopBannerVolume1h rows={top1hVolume?.rows || []} />
      </section>
      
    </div>
  );
}
