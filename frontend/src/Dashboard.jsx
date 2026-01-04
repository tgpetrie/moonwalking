import React, { useEffect, useMemo, useRef, useState } from "react";
import { useDataFeed } from "./hooks/useDataFeed";
import TopBannerScroll from "./components/TopBannerScroll";
import VolumeBannerScroll from "./components/VolumeBannerScroll";
import GainersTable1Min from "./components/GainersTable1Min.jsx";
import GainersTable3Min from "./components/GainersTable3Min";
import LosersTable3Min from "./components/LosersTable3Min";
import WatchlistPanel from "./components/WatchlistPanel.jsx";
import { useWatchlist } from "./context/WatchlistContext.jsx";
import SentimentPopupAdvanced from "./components/SentimentPopupAdvanced.jsx";
import AnomalyStream from "./components/AnomalyStream.jsx";

function formatTimestamp(d = new Date()) {
  const time = d.toLocaleTimeString([], {
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
  });
  const date = d.toLocaleDateString([], {
    month: "numeric",
    day: "numeric",
    year: "numeric",
  });
  return `${time} on ${date}`;
}

export default function Dashboard() {
  const { data: feedData } = useDataFeed();
  const payload = feedData?.data ?? feedData ?? {};
  const tsLabel = formatTimestamp(payload.updated_at ? new Date(payload.updated_at) : undefined);
  const [selectedSymbol, setSelectedSymbol] = useState(null);
  const updatedLabel = useMemo(() => {
    const raw = payload.updated_at;
    if (!raw) return "";
    const d = new Date(raw);
    if (Number.isNaN(d.getTime())) return String(raw);
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  }, [payload.updated_at]);
  const banner1h = useMemo(() => {
    return payload.banner_1h || payload.banner_1h_price || [];
  }, [payload.banner_1h, payload.banner_1h_price]);
  const vol1hTokens = useMemo(() => {
    const candidates =
      payload.banner_1h_volume ||
      payload.volume_1h ||
      payload.volume_1h_top ||
      payload.volume_1h_tokens ||
      [];
    const list = Array.isArray(candidates?.data) ? candidates.data : Array.isArray(candidates) ? candidates : [];
    return list.map((t) => ({
      symbol: t.symbol,
      volume_1h_delta: t.volume_1h_delta ?? t.volume_change_abs ?? t.volume_change ?? 0,
      volume_1h_pct: t.volume_1h_pct ?? t.volume_change_pct ?? t.change_1h_volume ?? 0,
    }));
  }, [payload.banner_1h_volume, payload.volume_1h, payload.volume_1h_top, payload.volume_1h_tokens]);

  const handleInfo = (symbol) => setSelectedSymbol(symbol);

  const { items: watchlistItems } = useWatchlist();
  const hasWatchlist = (watchlistItems?.length ?? 0) > 0;

  const boardRef = useRef(null);
  const showMoreRef = useRef(null);

  useEffect(() => {
    if (!boardRef.current || !showMoreRef.current) return;
    const boardRect = boardRef.current.getBoundingClientRect();
    const seamRect = showMoreRef.current.getBoundingClientRect();
    const centerY = seamRect.top + seamRect.height / 2 - boardRect.top;
    boardRef.current.style.setProperty("--rabbit-center-y", `${centerY}px`);
  }, [banner1h.length, vol1hTokens.length, payload.updated_at]);

  // Rabbit hover emitter (event delegation on the board)
  useEffect(() => {
    const board = boardRef.current;
    if (!board) return;

    const rabbit = board.querySelector(".rabbit-bg");
    if (!rabbit) return;

    let raf = 0;
    let active = false;

    const setEmitter = (clientX, clientY, on, side = null) => {
      const rr = rabbit.getBoundingClientRect();
      const x = Math.max(0, clientX - rr.left);
      const y = Math.max(0, clientY - rr.top);
      rabbit.style.setProperty("--bh-glow-x", `${x}px`);
      rabbit.style.setProperty("--bh-glow-y", `${y}px`);
      rabbit.style.setProperty("--bh-glow-a", on ? "1" : "0");

      const isLoser = typeof side === "string" && /loss|loser/i.test(side);
      rabbit.style.setProperty("--bh-glow-c", isLoser ? "var(--bh-loss)" : "var(--bh-gain)");

      // Toggle board-level bunny hover variable as a reliable fallback
      // so CSS can react to hover even if :has() is unsupported.
      try {
        if (board && board.style) {
          board.style.setProperty("--bh-bunny-hover", on ? "1" : "0");
        }
      } catch (err) {
        // silently ignore in older browsers
      }

      // temporary verification log removed

      active = Boolean(on);
    };

    const rowSelector = ".token-row.table-row, .bh-row";

    const onMove = (e) => {
      const row = e.target?.closest?.(rowSelector);
      if (!row || !board.contains(row)) {
        if (active) setEmitter(e.clientX, e.clientY, false);
        return;
      }
      const side = row.getAttribute?.("data-side") || null;
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => setEmitter(e.clientX, e.clientY, true, side));
    };

    const onOut = (e) => {
      const fromRow = e.target?.closest?.(rowSelector);
      const toRow = e.relatedTarget?.closest?.(rowSelector);
      if (fromRow && (!toRow || !board.contains(toRow))) {
        setEmitter(e.clientX, e.clientY, false);
      }
    };

    const onLeaveBoard = (e) => {
      setEmitter(e.clientX || 0, e.clientY || 0, false);
    };

    board.addEventListener("pointermove", onMove, { passive: true });
    board.addEventListener("pointerout", onOut, { passive: true });
    board.addEventListener("pointerleave", onLeaveBoard);

    return () => {
      cancelAnimationFrame(raf);
      board.removeEventListener("pointermove", onMove);
      board.removeEventListener("pointerout", onOut);
      board.removeEventListener("pointerleave", onLeaveBoard);
      rabbit.style.removeProperty("--bh-glow-x");
      rabbit.style.removeProperty("--bh-glow-y");
      rabbit.style.removeProperty("--bh-glow-a");
      rabbit.style.removeProperty("--bh-glow-c");
    };
  }, []);

  return (
    <main className="min-h-screen text-white relative overflow-x-hidden">
      {/* Bunny watermark */}
      <div aria-hidden className="pointer-events-none fixed inset-0 z-0 opacity-[0.08]">
        <div className="absolute inset-0 bg-[radial-gradient(1200px_700px_at_50%_30%,rgba(161,109,255,0.20),transparent_60%)]" />
      </div>

      <div className="relative z-10 max-w-6xl mx-auto px-4 sm:px-6 pt-8 pb-10">
        {/* Header cluster: timestamp • brand • status */}
        <header className="mb-6">
          <div className="flex items-start justify-between w-full">
            {/* timestamp chip */}
            <div>
              <div className="bg-black/70 border border-amber-300/50 rounded-full px-2 py-1 shadow-glowGold font-mono text-[10px] text-white/90 leading-none">
                Latest: {tsLabel}
              </div>
            </div>

            {/* brand center */}
            <div className="text-center flex flex-col items-center -mt-2">
              <div className="font-extrabold text-transparent bg-clip-text bg-gradient-to-br from-amber-400 to-amber-300 text-[48px] sm:text-[72px] leading-none drop-shadow-[0_0_18px_rgba(255,193,7,0.35)] tracking-tight">
                BHABIT
              </div>
              <div className="mt-2 font-bold text-transparent bg-clip-text bg-gradient-to-br from-purple-400 via-fuchsia-400 to-purple-700 text-[18px] sm:text-[28px] leading-none drop-shadow-[0_0_16px_rgba(162,75,255,0.35)] tracking-[0.35em]">
                PRØFITS  BÜ¥  IMPUL$€
              </div>
            </div>

            {/* actions cluster */}
            <div className="flex items-center gap-2 text-[10px] text-white/80">
              <button
                type="button"
                className="h-6 w-6 rounded-full bg-gradient-to-br from-purple-500 to-fuchsia-600 flex items-center justify-center text-[11px] text-white font-bold shadow-glowPurple"
                onClick={() => globalThis.location.reload()}
                aria-label="Refresh"
                title="Refresh"
              >
                ↻
              </button>
            </div>
          </div>
        </header>

        <div className="board-core" ref={boardRef}>
          <div className="rabbit-bg" aria-hidden />

          <section className="bh-banner-section">
            <div className="bh-banner-header">
              <div className="bh-banner-title">1-HOUR PRICE CHANGE</div>
              <div className="bh-banner-sub">
                <span className="bh-live">LIVE</span>
                <span className="bh-updated">Last updated {updatedLabel || "--"}</span>
              </div>
            </div>
            <TopBannerScroll />
          </section>

          <section className="bh-section">
            <div className="bh-section-title bh-section-title--center">1-MIN GAINERS</div>
            <div className="bh-section-body">
              <GainersTable1Min onInfo={handleInfo} />
            </div>
          </section>

          <div ref={showMoreRef} className="show-more-anchor" aria-hidden />

          <section className="bh-section">
            <div className="panel-3m-grid">
              <div className="bh-table-block">
                <div className="bh-section-title bh-section-title--center">TOP GAINERS (3M)</div>
                <div className="bh-section-body">
                  <GainersTable3Min onInfo={handleInfo} />
                </div>
              </div>
              <div className="bh-table-block">
                <div className="bh-section-title bh-section-title--center">TOP LOSERS (3M)</div>
                <div className="bh-section-body">
                  <LosersTable3Min onInfo={handleInfo} />
                </div>
              </div>
            </div>
          </section>

          <section className="mb-10">
            <div className="bh-panel bh-panel-full">
              <AnomalyStream
                data={payload}
                volumeData={payload.banner_1h_volume || payload.volume_1h || []}
              />
            </div>
          </section>

          {hasWatchlist && (
            <section className="panel-row-watchlist mb-10">
              <WatchlistPanel onInfo={handleInfo} />
            </section>
          )}

          <section className="bh-banner-section">
            <div className="bh-banner-header">
              <div className="bh-banner-title">1-HOUR VOLUME CHANGE</div>
            </div>
            <VolumeBannerScroll />
          </section>
        </div>
      </div>
      {selectedSymbol && (
        <SentimentPopupAdvanced
          isOpen={true}
          symbol={selectedSymbol}
          onClose={() => setSelectedSymbol(null)}
        />
      )}
    </main>
  );
}
