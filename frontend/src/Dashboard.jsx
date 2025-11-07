import React, { useEffect, useMemo, useState } from "react";
import TopBannerScroll from "./components/TopBannerScroll";
import VolumeBannerScroll from "./components/VolumeBannerScroll";
import GainersTable1Min from "./components/GainersTable1Min.jsx";
import GainersTable3Min from "./components/GainersTable3Min";
import LosersTable from "./components/LosersTable";
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
    console.log("[ui] fetching /data ...");
    fetch("/data")
      .then((r) => {
        console.log("[ui] /data status", r.status);
        return r.json();
      })
      .then((json) => {
        console.log("[ui] /data payload", json);
        setPayload(json);
      })
      .catch((err) => {
        console.error("[ui] /data error", err);
        setError(err.message);
      });
  }, []);

  const loading = !payload && !error;
  const data = payload?.data || {};
  const meta = payload?.meta || {};
  const errs = payload?.errors || {};

  const handleInfo = (symbol) => setSelectedSymbol(symbol);

  // simple banner bindings if present in /data
  const banner1h = useMemo(() => data.banner_1h || [], [data.banner_1h]);
  const vol1h = useMemo(() => data.volume_1h || [], [data.volume_1h]);

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

        {/* Section label + 1h banner */}
        <section className="mb-2">
          <div className="px-1 text-[11px] tracking-[0.15em] text-amber-400/90 uppercase">
            1H PRICE CHANGE • LIVE MARKET FEED
          </div>
        </section>
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

        {/* 3m gainers / losers side-by-side */}
        <section className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-10">
          <GainersTable3Min
            rows={data.gainers_3m || []}
            loading={loading}
            error={errs.gainers_3m}
            onInfo={handleInfo}
          />
          <LosersTable
            rows={data.losers_3m || []}
            loading={loading}
            error={errs.losers_3m}
            onInfo={handleInfo}
          />
        </section>

        {/* Bottom volume banner */}
        <section>
          <VolumeBannerScroll items={vol1h} />
        </section>
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
