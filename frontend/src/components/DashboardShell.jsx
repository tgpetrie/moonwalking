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
  const { gainers1m, gainers3m, losers3m, bannerVolume1h, bannerPrice1h, loading, error, lastUpdated, isValidating, fatal, coverage } = useDashboardData();
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

  // Pointer-driven dot emitter for the rabbit layer (event delegation on board)
  useEffect(() => {
    const board = boardRef.current;
    if (!board) return;

    const layer = board.querySelector(".rabbit-bg");
    if (!layer) return;

    let raf = 0;
    let active = false;

    const normSide = (raw) => {
      const v = String(raw || "").toLowerCase();
      if (v.includes("loss")) return "loser";
      return "gainer";
    };

    const setVars = (x, y, side, on) => {
      layer.style.setProperty("--bh-glow-a", on ? "1" : "0");
      layer.style.setProperty("--bh-glow-c", side === "loser" ? "var(--bh-loss)" : "var(--bh-gain)");
      layer.style.setProperty("--bh-glow-x", `${x}px`);
      layer.style.setProperty("--bh-glow-y", `${y}px`);
    };

    const update = (e) => {
      const row = e.target?.closest?.(".bh-row");
      if (!row || !board.contains(row)) {
        if (active) {
          active = false;
          layer.style.setProperty("--bh-glow-a", "0");
        }
        return;
      }

      const side =
        normSide(row.dataset.side) ||
        (row.classList.contains("is-loss") || row.classList.contains("bh-row--loss") ? "loser" : "gainer");

      const r = layer.getBoundingClientRect();
      const x = e.clientX - r.left;
      const y = e.clientY - r.top;

      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        active = true;
        setVars(x, y, side, true);
      });
    };

    const onMove = (e) => update(e);

    const onOut = (e) => {
      const fromRow = e.target?.closest?.(".bh-row");
      const toRow = e.relatedTarget?.closest?.(".bh-row");
      if (fromRow && (!toRow || !board.contains(toRow))) {
        active = false;
        layer.style.setProperty("--bh-glow-a", "0");
      }
    };

    const onLeaveBoard = () => {
      active = false;
      layer.style.setProperty("--bh-glow-a", "0");
    };

    board.addEventListener("pointermove", onMove, { passive: true });
    board.addEventListener("pointerout", onOut, { passive: true });
    board.addEventListener("pointerleave", onLeaveBoard);

    return () => {
      cancelAnimationFrame(raf);
      board.removeEventListener("pointermove", onMove);
      board.removeEventListener("pointerout", onOut);
      board.removeEventListener("pointerleave", onLeaveBoard);
    };
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
        <BoardWrapper highlightY={highlightY} highlightActive={highlightActive}>
          <div className="bh-board board-core" ref={boardRef}>
            <div className="rabbit-bg" aria-hidden="true" />
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

            {/* 1m and 3m Rail */}
            <div className="bh-rail">
              {/* 1-min Gainers */}
              <div className="board-section">
                <div className="board-section-header">
                  <div className="board-section-title">1 Minute Momentum – Live</div>
                  <div className="board-section-subtitle">Fastest short-term movers right now</div>
                </div>
                <div className="bh-linediv" aria-hidden="true">
                  <img src="/linediv.png" alt="" className="bh-linediv-img" />
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
                  <div className="board-section-title">3 Minute Leaderboard</div>
                  <div className="board-section-subtitle">Shorter bursts of momentum</div>
                </div>
                <div className="bh-linediv" aria-hidden="true">
                  <img src="/linediv.png" alt="" className="bh-linediv-img" />
                </div>
                <section className="panel-row--3m">
                  <div className="bh-panel bh-panel-half">
                    <div className="table-title">TOP GAINERS (3M)</div>
                    <div className="bh-linediv" aria-hidden="true">
                      <img src="/linediv.png" alt="" className="bh-linediv-img" />
                    </div>
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
                    <div className="bh-linediv" aria-hidden="true">
                      <img src="/linediv.png" alt="" className="bh-linediv-img" />
                    </div>
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
                  <div className="board-section-title">Your Watchlist</div>
                  <div className="board-section-subtitle">Track your favorite tokens</div>
                </div>
                <div className="bh-linediv" aria-hidden="true">
                  <img src="/linediv.png" alt="" className="bh-linediv-img" />
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
