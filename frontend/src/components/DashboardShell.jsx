// src/components/DashboardShell.jsx
import { useState, useEffect, useMemo } from "react";
import TopBannerScroll from "./TopBannerScroll.jsx";
import VolumeBannerScroll from "./VolumeBannerScroll.jsx";
import GainersTable1Min from "./GainersTable1Min.jsx";
import GainersTable3Min from "./GainersTable3Min.jsx";
import LosersTable3Min from "./LosersTable3Min.jsx";
import WatchlistPanel from "./WatchlistPanel.jsx";
import InsightsPanel from "./InsightsPanel.jsx";
import { LiveStatusBar } from "./LiveStatusBar.jsx";
import { useDashboardData } from "../hooks/useDashboardData";
import { useWatchlist } from "../context/WatchlistContext.jsx";
import BoardWrapper from "./BoardWrapper.jsx";

export default function DashboardShell({ onInfo }) {
  // Use centralized data hook with loading states
  const { gainers1m, gainers3m, losers3m, bannerVolume1h, bannerPrice1h, loading, error, lastUpdated, isValidating, fatal, coverage } = useDashboardData();
  const { items: watchlistItems, toggle: toggleWatchlist } = useWatchlist();
  const [insightsSymbol, setInsightsSymbol] = useState(null);
  const [highlightY, setHighlightY] = useState(50);
  const [highlightActive, setHighlightActive] = useState(false);
  const [mountedAt] = useState(() => Date.now());
  const [partialStreak, setPartialStreak] = useState(0);

  const handleInfo = (symbol) => {
    const sym = symbol?.toString()?.toUpperCase();
    if (sym) setInsightsSymbol(sym);
  };

  const handleToggleWatchlist = (symbol) => {
    toggleWatchlist({ symbol });
  };

  const watchlistSymbols = watchlistItems.map((item) => item.symbol);
  const onInfoProp = onInfo || handleInfo;

  const handleHoverHighlight = (percent = 50, active = false) => {
    setHighlightY(percent);
    setHighlightActive(active);
  };

  const counts = Object.values(coverage || {}).filter((v) => typeof v === "number");
  const total = counts.reduce((a, b) => a + b, 0);
  const hasZeros = counts.some((v) => v === 0);
  const isPartial = !fatal && (total === 0 || hasZeros);
  useEffect(() => {
    if (!lastUpdated) {
      setPartialStreak(0);
      return;
    }
    setPartialStreak((prev) => (isPartial ? prev + 1 : 0));
  }, [lastUpdated, isPartial]);

  // Derive `status` from live/partial/fatal indicators. Do not store as derived state
  const status = useMemo(() => {
    const now = Date.now();
    const isWarming = now - mountedAt < 25000;
    const isLive = !isPartial;
    if (fatal) return "DEGRADED";
    if (isLive) return "LIVE";
    if (isWarming) return "WARMING";
    if (partialStreak >= 2) return "PARTIAL";
    return "PARTIAL";
  }, [fatal, isPartial, mountedAt, partialStreak]);

  return (
    <div className="bh-app">
      <header className="bh-topbar">
        <div className="bh-logo">
          <span className="bh-logo-icon">🐇</span>
          <span className="bh-logo-text">BHABIT CB INSIGHT</span>
          <span className={`bh-status-pill bh-status-pill--${status.toLowerCase()}`}>{status}</span>
        </div>
        <div className="bh-topbar-right">
          <LiveStatusBar loading={loading} error={error} lastUpdated={lastUpdated} isValidating={isValidating} />
        </div>
      </header>

      <main className="bh-main">
        <div className="bh-bunny-layer" aria-hidden="true" />
        <BoardWrapper highlightY={highlightY} highlightActive={highlightActive}>
          <div className="bh-board">
            {/* 1h Price Banner (top) */}
            <section className="bh-board-row-full">
              <div className="board-section">
                <div className="board-section-header">
                  <div className="board-section-title">1 Hour Price Surge</div>
                  <div className="board-section-subtitle">Biggest price moves in the last hour</div>
                </div>
                <TopBannerScroll tokens={bannerPrice1h} />
              </div>
            </section>

            {/* 1-min Gainers (full-width or two-column, decided by component) */}
            <section className="bh-board-row-full">
              <div className="board-section">
                <div className="board-section-header">
                  <div className="board-section-title">1 Minute Momentum – Live</div>
                  <div className="board-section-subtitle">Fastest short-term movers right now</div>
                </div>
                <GainersTable1Min
                  tokens={gainers1m}
                  loading={loading}
                  onInfo={onInfoProp}
                  onToggleWatchlist={handleToggleWatchlist}
                  watchlist={watchlistSymbols}
                />
              </div>
            </section>

            {/* 3m Gainers / Losers (two-column) */}
            <div className="board-section">
              <div className="board-section-header">
                <div className="board-section-title">3 Minute Leaderboard</div>
                <div className="board-section-subtitle">Shorter bursts of momentum</div>
              </div>
              <section className="panel-row panel-row--3m">
                <div className="bh-panel bh-panel-half">
                  <div className="table-title">TOP GAINERS (3M)</div>
                  <GainersTable3Min
                    tokens={gainers3m}
                    loading={loading}
                    onInfo={onInfoProp}
                    onToggleWatchlist={handleToggleWatchlist}
                    watchlist={watchlistSymbols}
                  />
                </div>
                <div className="bh-panel bh-panel-half">
                  <div className="table-title">TOP LOSERS (3M)</div>
                  <LosersTable3Min
                    tokens={losers3m}
                    loading={loading}
                    onInfo={onInfoProp}
                    onToggleWatchlist={handleToggleWatchlist}
                    watchlist={watchlistSymbols}
                  />
                </div>
              </section>
            </div>

            {/* Watchlist (full-width) */}
            <section className="bh-board-row-full bh-row-watchlist">
              <div className="board-section">
                <div className="board-section-header">
                  <div className="board-section-title">Your Watchlist</div>
                  <div className="board-section-subtitle">Track your favorite tokens</div>
                </div>
                <div className="bh-row-block">
                  <WatchlistPanel onRowHover={handleHoverHighlight} />
                </div>
              </div>
            </section>

            {/* 1h Volume Banner (bottom) */}
            <section className="bh-board-row-full bh-row-volume">
              <div className="board-section">
                <div className="board-section-header">
                  <div className="board-section-title">Volume Surge – Last Hour</div>
                  <div className="board-section-subtitle">Highest trading activity</div>
                </div>
                <VolumeBannerScroll tokens={bannerVolume1h} />
              </div>
            </section>
          </div>
        </BoardWrapper>
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
