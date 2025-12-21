import React, { useEffect, useMemo, useRef, useState } from "react";
import { fetchAllData } from "./api.js";
import TopBannerScroll from "./components/TopBannerScroll";
import VolumeBannerScroll from "./components/VolumeBannerScroll";
import GainersTable1Min from "./components/GainersTable1Min.jsx";
import GainersTable3Min from "./components/GainersTable3Min";
import LosersTable3Min from "./components/LosersTable3Min";
import WatchlistPanel from "./components/WatchlistPanel.jsx";
import { useWatchlist } from "./context/WatchlistContext.jsx";
import AssetDetailPanel from "./components/AssetDetailPanel.jsx";

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
  const tsLabel = formatTimestamp();
  const [payload, setPayload] = useState(null);
  const [error, setError] = useState(null);
  const [selectedSymbol, setSelectedSymbol] = useState(null);

  useEffect(() => {
    // Use centralized API helper so calls respect VITE_API_BASE or the
    // DEFAULT_API_BASE fallback defined in `src/api.js`.
    let mounted = true;
    fetchAllData()
      .then((json) => {
        if (!mounted) return;
        setPayload(json);
      })
      .catch((err) => {
        if (!mounted) return;
        console.error("[ui] fetchAllData error", err);
        setError(err?.message || String(err));
      });
    return () => {
      mounted = false;
    };
  }, []);

  const loading = !payload && !error;
  const data = payload?.data || payload || {};
  const meta = payload?.meta || {};
  const errs = payload?.errors || {};

  const handleInfo = (symbol) => setSelectedSymbol(symbol);

  const { items: watchlistItems } = useWatchlist();
  const hasWatchlist = (watchlistItems?.length ?? 0) > 0;

  // simple banner bindings if present in /data (accept either `banner_1h` or `banner_1h_price`)
  const banner1h = useMemo(() => data.banner_1h || data.banner_1h_price || [], [data.banner_1h, data.banner_1h_price]);

  const vol1hTokens = useMemo(() => {
    const candidates =
      data.banner_1h_volume ||
      data.volume_1h ||
      data.volume_1h_top ||
      data.volume_1h_tokens ||
      [];
    const list = Array.isArray(candidates?.data) ? candidates.data : Array.isArray(candidates) ? candidates : [];
    return list.map((t) => ({
      symbol: t.symbol,
      volume_1h_delta: t.volume_1h_delta ?? t.volume_change_abs ?? t.volume_change ?? 0,
      volume_1h_pct: t.volume_1h_pct ?? t.volume_change_pct ?? t.change_1h_volume ?? 0,
    }));
  }, [data.banner_1h_volume, data.volume_1h, data.volume_1h_top, data.volume_1h_tokens]);

  const boardRef = useRef(null);
  const showMoreRef = useRef(null);

  useEffect(() => {
    if (!boardRef.current || !showMoreRef.current) return;
    const boardRect = boardRef.current.getBoundingClientRect();
    const seamRect = showMoreRef.current.getBoundingClientRect();
    const centerY = seamRect.top + seamRect.height / 2 - boardRect.top;
    boardRef.current.style.setProperty("--rabbit-center-y", `${centerY}px`);
  }, [banner1h?.length, vol1hTokens?.length, payload]);

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

      const side = normSide(row.dataset.side) ||
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
          {/* Section label + 1h banner */}
          <section className="mb-8">
            <TopBannerScroll items={banner1h} />
          </section>

          {/* 1-min gainers */}
          <section className="mb-10">
            <GainersTable1Min
              rows={data.gainers_1m || []}
              loading={loading}
              error={errs.gainers_1m}
              snapshotInfo={meta.gainers_1m}
              onInfo={handleInfo}
            />
          </section>

          {/* Anchor seam for rabbit centering */}
          <div ref={showMoreRef} className="show-more-anchor" aria-hidden />

          {/* 3m gainers / losers side-by-side */}
          <section className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-10">
            <GainersTable3Min
              rows={data.gainers_3m || []}
              loading={loading}
              error={errs.gainers_3m}
              onInfo={handleInfo}
            />
            <LosersTable3Min
              rows={data.losers_3m || []}
              loading={loading}
              error={errs.losers_3m}
              onInfo={handleInfo}
            />
          </section>

          {/* Optional Watchlist row (full-width under 3m) */}
          {hasWatchlist && (
            <section className="panel-row-watchlist mb-10">
              <WatchlistPanel onInfo={handleInfo} />
            </section>
          )}

          {/* Bottom volume banner */}
          <section>
            <VolumeBannerScroll tokens={vol1hTokens} />
          </section>
        </div>
      </div>
      {selectedSymbol && (
        <AssetDetailPanel
          symbol={selectedSymbol}
          onClose={() => setSelectedSymbol(null)}
        />
      )}
    </main>
  );
}
