import React from "react";
import TopBannerScroll from "./components/TopBannerScroll";
import VolumeBannerScroll from "./components/VolumeBannerScroll";
import GainersTable1Min from "./components/GainersTable1Min";
import GainersTable3Min from "./components/GainersTable3Min";
import LosersTable from "./components/LosersTable";
import useTransportStatus from "./hooks/useTransportStatus";
import useDataFeed from "./hooks/useDataFeed";

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
  const transportStatus = useTransportStatus?.() ?? "online";
  const offline = transportStatus === "offline";
  const statusLabel = offline ? "OFFLINE" : "LIVE";

  // data feed (polling) used to populate banners and tables
  const { banner1h, vol1h, gainers1m, gainers3m, losers3m } = useDataFeed();

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

            {/* status cluster */}
            <div className="flex items-center gap-2 text-[10px] text-white/80 font-mono">
              <button
                type="button"
                className="h-6 w-6 rounded-full bg-gradient-to-br from-purple-500 to-fuchsia-600 flex items-center justify-center text-[11px] text-white font-bold shadow-glowPurple"
                onClick={() => globalThis.location.reload()}
                aria-label="Refresh"
                title="Refresh"
              >
                ↻
              </button>
              <div className="h-[6px] w-16 bg-black/60 border border-fuchsia-500/50 rounded-[3px] shadow-glowPurple relative overflow-hidden">
                <div
                  className={`absolute left-0 top-0 h-full rounded-[2px] transition-all duration-300 ease-in-out ${
                    offline ? "bg-red-500" : "bg-fuchsia-500"
                  }`}
                  style={{ width: offline ? "15%" : "90%" }}
                />
              </div>
              <div
                className={`rounded-full px-2 py-[2px] leading-none text-[10px] font-bold uppercase ${
                  offline
                    ? "bg-red-600 text-white"
                    : "bg-black/70 border border-fuchsia-500/60 text-fuchsia-300 shadow-glowPurple"
                }`}
              >
                {statusLabel}
              </div>
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
          <GainersTable1Min items={gainers1m} />
        </section>

        {/* 3m gainers / losers side-by-side */}
        <section className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-10">
          <GainersTable3Min items={gainers3m} />
          <LosersTable items={losers3m} />
        </section>

        {/* Bottom volume banner */}
        <section>
          <VolumeBannerScroll items={vol1h} />
        </section>
      </div>
    </main>
  );
}
