import React from "react";
import TopBannerScroll from "./components/TopBannerScroll";
import VolumeBannerScroll from "./components/VolumeBannerScroll";
import GainersTable1Min from "./components/GainersTable1Min";
import GainersTable3Min from "./components/GainersTable3Min";
import LosersTable3Min from "./components/LosersTable3Min";
import useTransportStatus from "./hooks/useTransportStatus";

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
  const transportStatus = useTransportStatus();
  const offline = transportStatus === "offline";
  const statusLabel = offline ? "OFFLINE" : "LIVE";

  return (
    <div className="relative min-h-screen bg-black text-white font-mono text-[12px] leading-tight overflow-hidden">
      {/* bunny watermark */}
      <div className="pointer-events-none select-none absolute inset-0 flex items-center justify-center">
        <div className="w-[600px] h-[600px] bg-bunny bg-contain bg-center bg-no-repeat opacity-[0.07]" />
      </div>

      <div className="relative z-10 flex flex-col gap-6">
        {/* TOP BAR: timestamp + brand + status */}
        <header className="px-4 pt-4">
          <div className="flex items-start justify-between w-full max-w-6xl mx-auto">
            {/* timestamp */}
            <div className="flex">
              <div className="bg-bh.chipBg/80 border border-bh.borderGold rounded-full px-2 py-1 shadow-glowGold font-mono text-[10px] text-bh.textSoft leading-none">
                Latest: {tsLabel}
              </div>
            </div>

            {/* brand */}
            <div className="text-center flex flex-col items-center">
              <div className="font-bhTitle font-bold text-transparent bg-clip-text bg-gradient-to-br from-bh.gold to-bh.goldDim text-[40px] leading-none drop-shadow-[0_0_8px_rgba(249,200,107,0.6)] tracking-tight">
                BHABIT
              </div>
              <div className="mt-2 font-bhTagline font-bold text-transparent bg-clip-text bg-gradient-to-br from-bh.purple via-bh.purpleDim to-bh.bg text-[24px] leading-none drop-shadow-[0_0_8px_rgba(162,75,255,0.7)] tracking-[0.35em]">
                PRØFITS  BÜ¥  IMPUL$€
              </div>
            </div>

            {/* status cluster */}
            <div className="flex items-center gap-2 text-[10px] text-bh.textSoft font-mono">
              <button
                type="button"
                className="h-6 w-6 rounded-full bg-gradient-to-br from-bh.purple to-bh.purpleDim flex items-center justify-center text-[11px] text-bh.textMain font-bold shadow-glowPurple"
                onClick={() => globalThis.location.reload()}
                aria-label="Refresh"
              >
                ↻
              </button>

              <div className="h-[6px] w-16 bg-bh.chipBg border border-bh.purple rounded-[3px] shadow-glowPurple relative overflow-hidden">
                <div
                  className={`absolute left-0 top-0 h-full rounded-[2px] transition-all duration-300 ease-in-out ${
                    offline ? "bg-bh.danger" : "bg-bh.purple"
                  }`}
                  style={{ width: offline ? "15%" : "90%" }}
                />
              </div>

              <div
                className={`rounded-full px-2 py-[2px] leading-none text-[10px] font-bold uppercase ${
                  offline
                    ? "bg-bh.danger text-bh.textMain"
                    : "bg-bh.chipBg border border-bh.purple text-bh.purple shadow-glowPurple"
                }`}
              >
                {statusLabel}
              </div>
            </div>
          </div>
        </header>

        {/* SECTION LABEL + TICKERS */}
        <section className="px-4">
          <div className="text-[11px] tracking-[0.15em] text-white/80 uppercase">
            1H PRICE CHANGE • LIVE MARKET FEED
          </div>

          <div className="mt-3 space-y-1">
            <TopBannerScroll />
            <VolumeBannerScroll />
          </div>
        </section>

        {/* MAIN GRID */}
        <section className="px-4 pb-16 flex flex-col gap-12 items-center">
          <div className="w-full max-w-4xl">
            <GainersTable1Min />
          </div>

          <div className="w-full max-w-5xl grid grid-cols-1 md:grid-cols-2 gap-12">
            <div className="flex justify-start">
              <GainersTable3Min />
            </div>
            <div className="flex justify-start">
              <LosersTable3Min />
            </div>
          </div>
        </section>
      </div>

      {/* floating helper button */}
      <button
        type="button"
        className="fixed right-4 bottom-4 h-10 w-10 rounded-full bg-gradient-to-br from-bh.purple to-bh.purpleDim text-bh.textMain text-xl font-bold shadow-glowPurple flex items-center justify-center"
        onClick={() => console.log("idea / assistant / help clicked")}
        aria-label="Assistant"
      >
        💡
      </button>
    </div>
  );
}
