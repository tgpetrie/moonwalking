// src/components/DashboardShell.jsx
import { useState, useEffect, useMemo, useRef } from "react";
import VolumeBannerScroll from "./VolumeBannerScroll.jsx";
import TopBannerScroll from "./TopBannerScroll.jsx";
import GainersTable1Min from "./GainersTable1Min.jsx";
import GainersTable3Min from "./GainersTable3Min.jsx";
import LosersTable3Min from "./LosersTable3Min.jsx";
import WatchlistPanel from "./WatchlistPanel.jsx";
import SentimentPopupAdvanced from "./SentimentPopupAdvanced.jsx";
import AnomalyStream from "./AnomalyStream.jsx";
import { useDashboardData } from "../hooks/useDashboardData";
import { useWatchlist } from "../context/WatchlistContext.jsx";
import BoardWrapper from "./BoardWrapper.jsx";
import AlertsDock from "./AlertsDock.jsx";

export default function DashboardShell({ onInfo }) {
  const BANNER_SPEED = 36;
  // Use centralized data hook with loading states
  const { gainers1m, gainers3m, losers3m, bannerVolume1h, bannerPrice1h, alerts, loading, error, lastUpdated, fatal, coverage, warming, warming3m, staleSeconds, partial, lastGoodTs } = useDashboardData();
  const { items: watchlistItems, toggle: toggleWatchlist } = useWatchlist();
  const [sentimentSymbol, setSentimentSymbol] = useState(null);
  const [sentimentOpen, setSentimentOpen] = useState(false);
  const [highlightY, setHighlightY] = useState(50);
  const [highlightActive, setHighlightActive] = useState(false);
  const [mountedAt] = useState(() => Date.now());
  const partialStreakRef = useRef(0);
  const boardRef = useRef(null);
  const boardShellRef = useRef(null);

  // Bunny hover emitter (row-only, no shell vars)
  useEffect(() => {
    const board = boardRef.current;
    if (!board) return;

    const rowSelector = ".bh-row, .token-row.table-row";
    let hotRow = null;

    const clearHot = () => {
      if (hotRow) {
        hotRow.classList.remove("bh-row--hot");
        hotRow.style.removeProperty("--bh-row-hover-r");
        hotRow.style.removeProperty("--bh-row-hover-x");
        hotRow.style.removeProperty("--bh-row-hover-y");
        hotRow = null;
      }
    };

    const setHot = (row, clientX, clientY) => {
      if (!row) return clearHot();

      if (row !== hotRow) {
        clearHot();
        hotRow = row;
        row.classList.add("bh-row--hot");
      }

      const r = row.getBoundingClientRect();
      const radius = Math.max(90, Math.min(220, r.height * 1.15));
      const x = Math.max(0, Math.min(r.width, clientX - r.left));
      const y = Math.max(0, Math.min(r.height, clientY - r.top));
      row.style.setProperty("--bh-row-hover-r", `${radius}px`);
      row.style.setProperty("--bh-row-hover-x", `${x}px`);
      row.style.setProperty("--bh-row-hover-y", `${y}px`);
    };

    const onMove = (e) => {
      const row = e.target?.closest?.(rowSelector);
      if (!row || !board.contains(row)) return clearHot();
      setHot(row, e.clientX, e.clientY);
    };

    const onLeaveBoard = () => {
      clearHot();
    };

    board.addEventListener("pointermove", onMove, { passive: true });
    board.addEventListener("pointerleave", onLeaveBoard);

    return () => {
      board.removeEventListener("pointermove", onMove);
      board.removeEventListener("pointerleave", onLeaveBoard);
      clearHot();
    };
  }, []);

  const handleInfo = (symbol) => {
    const sym = symbol?.toString()?.toUpperCase();
    if (sym) {
      console.log("INFO_CLICK", sym);
      setSentimentSymbol(sym);
      setSentimentOpen(true);
    }
  };

  const handleToggleWatchlist = (symbol, price = null) => {
    toggleWatchlist({ symbol, price });
  };

  const watchlistSymbols = watchlistItems.map((item) => item.symbol);
  const onInfoProp = onInfo || handleInfo;
  const uiLoading = loading || warming;

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
      if (!e.detail) return;
      const sym = String(e.detail).toUpperCase();
      console.log("INFO_CLICK", sym);
      setSentimentSymbol(sym);
      setSentimentOpen(true);
    };
    window.addEventListener("openInfo", handler);
    return () => window.removeEventListener("openInfo", handler);
  }, []);

  // Derive `status` from live/partial/fatal indicators. Do not store as derived state
  const formatTempTime = (value) => {
    if (!value) return "—";                                                                        
    const date = value instanceof Date ? value : new Date(value);
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  };

  const STALE_THRESHOLD = 20; // seconds

  const status = useMemo(() => {
    const coreReady = (gainers1m?.length || 0) > 0 || (gainers3m?.length || 0) > 0 || (losers3m?.length || 0) > 0;
    const isStale = staleSeconds !== null && staleSeconds > STALE_THRESHOLD;

    if (fatal) return "DEGRADED";
    if (error && !coreReady) return "OFFLINE";
    if (warming) return "WARMING";
    if (isStale) return "STALE";
    if (!coreReady && partialStreak >= 2) return "DEGRADED";

    return "LIVE";
  }, [fatal, error, warming, staleSeconds, partialStreak, gainers1m, gainers3m, losers3m]);

  const lastUpdatedLabel = useMemo(
    () => formatTempTime(lastUpdated || lastGoodTs),
    [lastUpdated, lastGoodTs]
  );

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
          <div className="live-status">
            <span className={`bh-status-pill bh-status-pill--${status.toLowerCase()}`}>{status}</span>
            <span className="live-updated">
              <span className="live-updated-time">{lastUpdatedLabel}</span>
            </span>
            {status === "WARMING" ? (
              <span className="live-warming">Warming up data…</span>
            ) : null}
          </div>
        </div>
      </header>

      {/* 1 Hour Price Change Banner - Full Width */}
      <div className="bh-banner-block">
        <div className="bh-banner-label">1H PRICE</div>
        <TopBannerScroll tokens={bannerPrice1h} loading={uiLoading} speed={BANNER_SPEED} />
      </div>

      <main className="bh-main">
        <BoardWrapper highlightY={highlightY} highlightActive={highlightActive}>
          <div ref={boardShellRef} className="bh-board-shell" data-board-hover="0">
            <div ref={boardRef} className="bh-board board-core">
              <div className="rabbit-bg" aria-hidden="true" />

              {/* 1m and 3m Rail */}
              <div className="bh-rail">
                <div className="bh-rail-stack">
                  {/* 1-min Gainers */}
                  <section className="bh-board-row-full">
                    <div className="bh-panel bh-panel--rail">
                      <div className="board-section">
                        <div className="board-section-header board-section-header--center">
                          <div className="board-section-title board-section-title--center">TOP MOVERS (1M)</div>
                        </div>
                        <GainersTable1Min
                          tokens={gainers1m}
                          loading={uiLoading}
                          onInfo={onInfoProp}
                          onToggleWatchlist={handleToggleWatchlist}
                          watchlist={watchlistSymbols}
                        />
                      </div>
                    </div>
                  </section>

                  {/* 3m Gainers / Losers */}
                  <div className="board-section">
                    <section className="bh-3m-grid">
                      <div className="bh-panel bh-panel-half">
                        <div className="table-title">TOP GAINERS (3M)</div>
                        <GainersTable3Min
                          tokens={gainers3m}
                          loading={uiLoading}
                          warming3m={warming3m}
                          onInfo={onInfoProp}
                          onToggleWatchlist={handleToggleWatchlist}
                          watchlist={watchlistSymbols}
                        />
                      </div>
                      <div className="bh-panel bh-panel-half">
                        <div className="table-title">TOP LOSERS (3M)</div>
                        <LosersTable3Min
                          tokens={losers3m}
                          loading={uiLoading}
                          warming3m={warming3m}
                          onInfo={onInfoProp}
                          onToggleWatchlist={handleToggleWatchlist}
                          watchlist={watchlistSymbols}
                        />
                      </div>
                    </section>
                  </div>

                  {/* Anomaly Stream - Intelligence Log */}
                  <section className="bh-board-row-full">
                    <div className="bh-panel bh-panel--rail">
                      <AnomalyStream
                        data={{ gainers_1m: gainers1m, losers_3m: losers3m, alerts: alerts || [], updated_at: lastUpdated }}
                        volumeData={bannerVolume1h || []}
                      />
                    </div>
                  </section>

                  {/* Watchlist (full-width) */}
                  <section className="bh-board-row-full bh-row-watchlist">
                    <div className="bh-panel bh-panel--rail">
                      <div className="board-section">
                        <div className="board-section-header">
                          <div className="board-section-title">Watchlist</div>
                        </div>
                        <div className="bh-row-block">
                          <WatchlistPanel onRowHover={handleHoverHighlight} onInfo={onInfoProp} />
                        </div>
                      </div>
                    </div>
                  </section>
                </div>
              </div>
            </div>
          </div>
        </BoardWrapper>
      </main>

      {/* 1 Hour Volume Banner - Full Width */}
      <div className="bh-banner-block">
        <div className="bh-banner-label">1H VOLUME</div>
        <VolumeBannerScroll tokens={bannerVolume1h} loading={uiLoading} speed={BANNER_SPEED} />
      </div>

      {/* Insights floating card aligned to board rails */}
      <SentimentPopupAdvanced
        key={sentimentSymbol || "GLOBAL"}
        isOpen={sentimentOpen}
        symbol={sentimentSymbol || undefined}
        onClose={() => {
          setSentimentOpen(false);
          setSentimentSymbol(null);
        }}
      />

      <AlertsDock />
    </div>
  );
}
