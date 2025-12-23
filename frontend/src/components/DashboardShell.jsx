// src/components/DashboardShell.jsx
import { useState, useEffect, useMemo, useRef } from "react";
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
  const { gainers1m, gainers3m, losers3m, bannerVolume1h, bannerPrice1h, loading, error, lastUpdated, isValidating, fatal, coverage, heartbeatPulse, lastFetchTs } = useDashboardData();
  const { items: watchlistItems, toggle: toggleWatchlist } = useWatchlist();
  const [insightsSymbol, setInsightsSymbol] = useState(null);
  const [highlightY, setHighlightY] = useState(50);
  const [highlightActive, setHighlightActive] = useState(false);
  const [mountedAt] = useState(() => Date.now());
  const partialStreakRef = useRef(0);
  const boardRef = useRef(null);

  const handleInfo = (symbol) => {
    const sym = symbol?.toString()?.toUpperCase();
    if (sym) setInsightsSymbol(sym);
  };

  const handleToggleWatchlist = (symbol, price = null) => {
    toggleWatchlist({ symbol, price });
  };

  const watchlistSymbols = watchlistItems.map((item) => item.symbol);
  const onInfoProp = onInfo || handleInfo;

  const handleHoverHighlight = (percent = 50, active = false) => {
    setHighlightY(percent);
    setHighlightActive(active);
  };

  // Removed global rabbit-hot wake handlers — reveal is per-row via CSS backdrop-filter

  const counts = Object.values(coverage || {}).filter((v) => typeof v === "number");
  const total = counts.reduce((a, b) => a + b, 0);
  const hasZeros = counts.some((v) => v === 0);
  const isPartial = !fatal && (total === 0 || hasZeros);
  const partialStreak = useMemo(() => {
    if (!lastUpdated) {
      return 0;
    }
    return isPartial ? partialStreakRef.current + 1 : 0;
  }, [lastUpdated, isPartial]);
  useEffect(() => {
    partialStreakRef.current = partialStreak;
  }, [partialStreak]);

  // Listen for "openInfo" events from anywhere (e.g. TokenRowUnified)
  useEffect(() => {
    const handler = (e) => {
      if (e.detail) setInsightsSymbol(e.detail);
    };
    window.addEventListener("openInfo", handler);
    return () => window.removeEventListener("openInfo", handler);
  }, []);

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

  const tickerItems = useMemo(() => {
    if (!gainers1m?.length) return ["Waiting for live data…"];
    return gainers1m.slice(0, 5).map((row) => {
      const pct =
        Number(row?.change_1m ?? row?.price_change_1m ?? row?.change_pct ?? row?.pct_change ?? 0) || 0;
      const formatted = pct.toFixed(2);
      const sign = pct > 0 ? "+" : pct < 0 ? "" : "";
      const symbol = row?.symbol ?? row?.ticker ?? "—";
      return `${symbol} ${sign}${formatted}%`;
    });
  }, [gainers1m]);

  return (
    <div className="bh-app">
      <header className="bh-topbar">
        <div className="bh-logo">
          <span className="bh-logo-icon">🐇</span>
          <span className="bh-logo-text">BHABIT CB INSIGHT</span>
          <span className={`bh-status-pill bh-status-pill--${status.toLowerCase()}`}>{status}</span>
        </div>
        <div className="bh-topbar-right">
          <LiveStatusBar
            loading={loading}
            error={error}
            lastUpdated={lastUpdated}
            isValidating={isValidating}
            heartbeatPulse={heartbeatPulse}
            lastFetchTs={lastFetchTs}
          />
        </div>
      </header>

      <div className="live-ticker" aria-live="polite">
        <span className="live-ticker-label">Live ticker</span>
        <div className="live-ticker-track" role="presentation">
          {[...tickerItems, ...tickerItems].map((item, idx) => (
            <span key={`${item}-${idx}`} className="live-ticker-item">
              {item}
            </span>
          ))}
        </div>
      </div>

      <main className="bh-main">
        <BoardWrapper highlightY={highlightY} highlightActive={highlightActive}>
          <div ref={boardRef} className="bh-board board-core">
            <div className="rabbit-bg" aria-hidden="true" />
            {/* 1h Price Banner (top) */}
            <section className="bh-board-row-full">
              <div className="board-section">
                <div className="board-section-header">
                  <div className="board-section-title">1 Hour Price %</div>
                </div>
                <TopBannerScroll tokens={bannerPrice1h} />
              </div>
            </section>

            {/* 1m and 3m Rail */}
            <div className="bh-rail">
              {/* 1-min Gainers */}
              <div className="board-section">
                <div className="board-section-header">
                  <div className="board-section-title">1 Min Gainers</div>
                </div>
                <GainersTable1Min
                  tokens={gainers1m}
                  loading={loading}
                  onInfo={onInfoProp}
                  onToggleWatchlist={handleToggleWatchlist}
                  watchlist={watchlistSymbols}
                />
              </div>

              {/* 3m Gainers / Losers */}
              <div className="board-section">
                <div className="board-section-header">
                  <div className="board-section-title">3 Min Gainers/Losers</div>
                </div>
                <section className="panel-row--3m">
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
            </div>

            {/* Watchlist (full-width) */}
            <section className="bh-board-row-full bh-row-watchlist">
              <div className="board-section">
                <div className="board-section-header">
                  <div className="board-section-title">Watchlist</div>
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
                  <div className="board-section-title">1 Hour Volume</div>
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
