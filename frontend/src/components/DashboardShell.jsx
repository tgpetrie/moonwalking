// src/components/DashboardShell.jsx
import { useState, useEffect, useMemo, useRef } from "react";
import VolumeBannerScroll from "./VolumeBannerScroll.jsx";
import TopBannerScroll from "./TopBannerScroll.jsx";
import SentimentPopupAdvanced from "./SentimentPopupAdvanced.jsx";
import AlertsPanelGlobal from "./AlertsPanelGlobal.jsx";
import AnomalyStream from "./AnomalyStream.jsx";
import { useDashboardData } from "../hooks/useDashboardData";
import { useWatchlist } from "../context/WatchlistContext.jsx";
import AlertsDock from "./AlertsDock.jsx";
import AskBhabitPanel from "./AskBhabitPanel.jsx";
import { getMarketPressure } from "../utils/marketPressure";
import BoardWrapper from "./BoardWrapper.jsx";
import GainersTable1Min from "./GainersTable1Min.jsx";
import GainersTable3Min from "./GainersTable3Min.jsx";
import LosersTable3Min from "./LosersTable3Min.jsx";
import WatchlistPanel from "./WatchlistPanel.jsx";
import { ROW_CUE_LEGEND } from "../utils/rowCue.js";

const BOARD_MOVEMENT_LEGEND = [
  {
    symbol: "+2 / -2",
    tone: "neutral",
    label: "Board rank shift",
    detail: "Position changed on the board. This is not price direction.",
  },
  {
    symbol: "2↑ / 2↓",
    tone: "neutral",
    label: "Losers board shift",
    detail: "Moved up or down the losers list. Still a rank change, not price direction.",
  },
];

const BOARD_ACTION_LEGEND = [
  {
    kind: "star",
    tone: "neutral",
    label: "Watchlist star",
    detail: "Empty means not pinned. Filled means the coin is on your watchlist.",
  },
  {
    kind: "trade",
    tone: "neutral",
    label: "Trade button",
    detail: "Open Coinbase Advanced Trade in a new tab.",
  },
];

function LegendStarIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" className="bh-board-help__action-svg">
      <polygon points="12,2 15,9 22,9.5 17,14.5 18.5,22 12,18 5.5,22 7,14.5 2,9.5 9,9" />
    </svg>
  );
}

function LegendTradeIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="bh-board-help__action-svg">
      <circle cx="12" cy="12" r="10" />
      <path d="M14.8 8.3c-.6-.8-1.6-1.3-2.8-1.3-1.8 0-3 1-3 2.4 0 1.6 1.3 2.1 2.9 2.5 1.7.4 3.1.8 3.1 2.5 0 1.4-1.2 2.6-3.2 2.6-1.3 0-2.5-.5-3.3-1.5" />
      <line x1="12" y1="5.7" x2="12" y2="18.3" />
    </svg>
  );
}

function LegendPersistenceIcon() {
  return (
    <span className="bh-board-help__persist" aria-hidden="true">
      <span className="bh-board-help__persist-dot" />
      <span className="bh-board-help__persist-count">3x</span>
    </span>
  );
}

function BoardRowLegend() {
  return (
    <details className="bh-board-help">
      <summary className="bh-board-help__toggle">Row legend</summary>
      <div className="bh-board-help__popover" role="note">
        <div className="bh-board-help__title">How to read the row symbols</div>
        <div className="bh-board-help__note bh-board-help__note--lead">
          Each row can show one current cue, one recent-memory cue from the last few minutes, and one persistence marker.
        </div>

        <section className="bh-board-help__section" aria-label="Cue symbols">
          <div className="bh-board-help__section-title">Cue Symbols</div>
          <div className="bh-board-help__grid">
            {ROW_CUE_LEGEND.map((item) => (
              <div key={item.key} className="bh-board-help__row">
                <span className={`bh-board-help__icon bh-board-help__icon--${item.tone}`} aria-hidden="true">
                  {item.emoji}
                </span>
                <span className="bh-board-help__copy">
                  <span className="bh-board-help__label">{item.label}</span>
                  <span className="bh-board-help__desc">{item.detail}</span>
                </span>
              </div>
            ))}
          </div>
        </section>

        <section className="bh-board-help__section" aria-label="Recent context markers">
          <div className="bh-board-help__section-title">Recent Context</div>
          <div className="bh-board-help__row">
            <span className="bh-board-help__icon bh-board-help__icon--neutral" aria-hidden="true">
              ◉
            </span>
            <span className="bh-board-help__copy">
              <span className="bh-board-help__label">Secondary recent cue</span>
              <span className="bh-board-help__desc">
                A smaller second icon means this coin had another meaningful alert recently, even if that is not why it is on the board right now.
              </span>
            </span>
          </div>
          <div className="bh-board-help__row">
            <span className="bh-board-help__icon bh-board-help__icon--persistence" aria-hidden="true">
              <LegendPersistenceIcon />
            </span>
            <span className="bh-board-help__copy">
              <span className="bh-board-help__label">Persistence marker</span>
              <span className="bh-board-help__desc">
                Small BHABIT-purple dot means repeat or consecutive board presence. A tiny count appears only for stronger persistence.
              </span>
            </span>
          </div>
        </section>

        <section className="bh-board-help__section" aria-label="Board movement markers">
          <div className="bh-board-help__section-title">Board Movement</div>
          {BOARD_MOVEMENT_LEGEND.map((item) => (
            <div key={item.symbol} className="bh-board-help__row">
              <span className={`bh-board-help__icon bh-board-help__icon--${item.tone}`} aria-hidden="true">
                {item.symbol}
              </span>
              <span className="bh-board-help__copy">
                <span className="bh-board-help__label">{item.label}</span>
                <span className="bh-board-help__desc">{item.detail}</span>
              </span>
            </div>
          ))}
        </section>

        <div className="bh-board-help__note">Click any non-icon part of a row to open that coin's detail view.</div>

        <section className="bh-board-help__section" aria-label="Row actions">
          <div className="bh-board-help__section-title">Row Actions</div>
          {BOARD_ACTION_LEGEND.map((item) => (
            <div key={item.kind} className="bh-board-help__row">
              <span className={`bh-board-help__icon bh-board-help__icon--${item.tone}`} aria-hidden="true">
                {item.kind === "star" ? <LegendStarIcon /> : <LegendTradeIcon />}
              </span>
              <span className="bh-board-help__copy">
                <span className="bh-board-help__label">{item.label}</span>
                <span className="bh-board-help__desc">{item.detail}</span>
              </span>
            </div>
          ))}
        </section>
      </div>
    </details>
  );
}

export default function DashboardShell({ onInfo }) {
  const BANNER_SPEED = 36;
  // Use centralized data hook with loading states
  const { gainers1m, gainers3m, losers3m, bannerVolume1h, bannerPrice1h, alerts, loading, error, lastUpdated, fatal, coverage, warming, warming3m, staleSeconds, partial, lastGoodTs, alertsMeta } = useDashboardData();
  const { items: watchlistItems, toggle: toggleWatchlist } = useWatchlist();
  const [sentimentSymbol, setSentimentSymbol] = useState(null);
  const [sentimentOpen, setSentimentOpen] = useState(false);
  const [sentimentDefaultTab, setSentimentDefaultTab] = useState("coin");
  const [alertsOpen, setAlertsOpen] = useState(false);
  const partialStreakRef = useRef(0);
  const boardRef = useRef(null);

  // Clear board-level hover state when leaving the board.
  // Row components own the active hover coordinates.
  useEffect(() => {
    const board = boardRef.current || document.querySelector(".board-core");
    if (!board) return;

    const onLeaveBoard = () => {
      board.setAttribute("data-row-hover", "0");
    };

    board.addEventListener("pointerleave", onLeaveBoard);

    return () => {
      board.removeEventListener("pointerleave", onLeaveBoard);
    };
  }, []);

  useEffect(() => {
    const board = boardRef.current;
    if (!board) return;
    const target =
      board.querySelector(".bh-rail") ||
      board.querySelector(".bh-rail-stack") ||
      board.querySelector(".bh-board") ||
      board;

    const updateMuralCenter = () => {
      const b = board.getBoundingClientRect();
      const t = target.getBoundingClientRect();
      const bw = b.width || 1;
      const bh = b.height || 1;
      const x = Math.max(0, Math.min(100, ((t.left + t.width / 2 - b.left) / bw) * 100));
      const y = Math.max(0, Math.min(100, ((t.top + t.height * 0.20 - b.top) / bh) * 100));
      board.style.setProperty("--mural-pos-x", `${x}%`);
      board.style.setProperty("--mural-pos-y", `${y}%`);
    };

    updateMuralCenter();

    let ro = null;
    if (typeof ResizeObserver !== "undefined") {
      ro = new ResizeObserver(updateMuralCenter);
      ro.observe(board);
      if (target !== board) {
        ro.observe(target);
      }
    }

    window.addEventListener("resize", updateMuralCenter, { passive: true });
    window.addEventListener("scroll", updateMuralCenter, { passive: true });

    return () => {
      if (ro) ro.disconnect();
      window.removeEventListener("resize", updateMuralCenter);
      window.removeEventListener("scroll", updateMuralCenter);
    };
  }, []);

  const handleInfo = (symbol) => {
    const sym = symbol?.toString()?.toUpperCase();
    if (sym) {
      console.log("INFO_CLICK", sym);
      setSentimentSymbol(sym);
      setSentimentDefaultTab("coin");
      setSentimentOpen(true);
    }
  };

  const handleOpenAlerts = () => {
    setAlertsOpen(true);
  };

  const handleToggleWatchlist = (symbol, price = null) => {
    toggleWatchlist({ symbol, price });
  };

  const watchlistSymbols = watchlistItems.map((item) => item.symbol);
  const onInfoProp = onInfo || handleInfo;
  const uiLoading = loading || warming;

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
      setSentimentDefaultTab("coin");
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

  const pressurePill = useMemo(() => {
    const mp = getMarketPressure({ market_pressure: alertsMeta?.market_pressure });
    const h = Number(mp.index ?? 50);
    const tone = h >= 65 ? "hot" : h >= 45 ? "warm" : "cold";
    const label = h >= 80 ? "EXTREME" : h >= 65 ? "HOT" : h >= 45 ? "WARM" : h >= 25 ? "COOL" : "COLD";
    return { value: h, tone, label };
  }, [alertsMeta?.market_pressure]);

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
            {alertsMeta.market_pressure ? (
              <span className={`bh-pressure-pill bh-pressure-pill--${pressurePill.tone}`} title={`Market Pressure: ${pressurePill.value.toFixed(0)}`}>
                {pressurePill.label} {pressurePill.value.toFixed(0)}
              </span>
            ) : null}
            {status === "WARMING" ? (
              <span className="live-warming">Warming up data…</span>
            ) : null}
          </div>
        </div>
        <div className="bh-topbar-right">
          <a href="/login" className="bh-topbar-link bh-topbar-link--ghost">
            Login
          </a>
          <a href="/signup" className="bh-topbar-link bh-topbar-link--primary">
            Sign Up
          </a>
        </div>
      </header>

      <div ref={boardRef} className="board-core mw-board" data-board="1">
        <div className="rabbit-bg" aria-hidden="true" />

        {/* 1 Hour Price Change Banner - Full Width */}
        <div className="bh-banner-block">
          <div className="bh-banner-label">1H PRICE</div>
          <TopBannerScroll tokens={bannerPrice1h} loading={uiLoading} speed={BANNER_SPEED} />
        </div>

        <main className="bh-main">
          <BoardWrapper>
            <div className="bh-board-shell" data-board-hover="0">
              <div className="bh-board">
                <div className="bh-rail">
                  <div className="bh-rail-stack">
                    <div className="bh-board-legend-bar">
                      <BoardRowLegend />
                    </div>

                    <section className="bh-board-row-full">
                      <div className="bh-panel bh-panel--rail" data-hover-origin="center">
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

                    <div className="board-section">
                      <section className="bh-3m-grid">
                        <div className="bh-panel bh-panel-half" data-hover-origin="right">
                          <div className="board-section">
                            <div className="board-section-header board-section-header--center">
                              <div className="board-section-title board-section-title--center">TOP GAINERS (3M)</div>
                            </div>
                            <GainersTable3Min
                              tokens={gainers3m}
                              loading={uiLoading}
                              warming3m={warming3m}
                              onInfo={onInfoProp}
                              onToggleWatchlist={handleToggleWatchlist}
                              watchlist={watchlistSymbols}
                            />
                          </div>
                        </div>
                        <div className="bh-panel bh-panel-half" data-hover-origin="left">
                          <div className="board-section">
                            <div className="board-section-header board-section-header--center">
                              <div className="board-section-title board-section-title--center">TOP LOSERS (3M)</div>
                            </div>
                            <LosersTable3Min
                              tokens={losers3m}
                              loading={uiLoading}
                              warming3m={warming3m}
                              onInfo={onInfoProp}
                              onToggleWatchlist={handleToggleWatchlist}
                              watchlist={watchlistSymbols}
                            />
                          </div>
                        </div>
                      </section>
                    </div>

                    <section className="bh-board-row-full">
                      <div className="bh-panel bh-panel--rail">
                        <AnomalyStream
                          data={{ gainers_1m: gainers1m, losers_3m: losers3m, alerts: alerts || [], updated_at: lastUpdated }}
                          volumeData={bannerVolume1h || []}
                        />
                      </div>
                    </section>

                    <section className="bh-board-row-full bh-row-watchlist">
                      <div className="bh-panel bh-panel--rail">
                        <div className="board-section">
                          <div className="board-section-header">
                            <div className="board-section-title">Watchlist</div>
                          </div>
                          <div className="bh-row-block">
                            <WatchlistPanel onInfo={onInfoProp} />
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
      </div>

      {/* Insights floating card aligned to board rails */}
      <SentimentPopupAdvanced
        key={`${sentimentSymbol || "GLOBAL"}-${sentimentDefaultTab}`}
        isOpen={sentimentOpen}
        symbol={sentimentSymbol || undefined}
        defaultTab={sentimentDefaultTab}
        onClose={() => {
          setSentimentOpen(false);
          setSentimentSymbol(null);
          setSentimentDefaultTab("coin");
        }}
      />

      <AlertsPanelGlobal
        isOpen={alertsOpen}
        onClose={() => setAlertsOpen(false)}
        onOpenCoinSentiment={(symbol) => {
          handleInfo(symbol);
          setAlertsOpen(false);
        }}
      />

      <AskBhabitPanel />
      <AlertsDock onOpenAlerts={handleOpenAlerts} />
    </div>
  );
}
