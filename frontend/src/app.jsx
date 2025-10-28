import React from "react";
import TopBannerScroll from "./components/TopBannerScroll";
import GainersTable1Min from "./components/GainersTable1Min";
import GainersTable3Min from "./components/GainersTable3Min";
import LosersTable3Min from "./components/LosersTable3Min";
import VolumeBannerScroll from "./components/VolumeBannerScroll";
import useTransportStatus from "./hooks/useTransportStatus.js";

// little formatter helper like the screenshot
function formatTimestamp(d = new Date()) {
  const t = d.toLocaleTimeString([], {
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
  });
  const day = d.toLocaleDateString([], {
    month: "numeric",
    day: "numeric",
    year: "numeric",
  });
  return `${t} on ${day}`;
}

export default function App() {
  const tsLabel = formatTimestamp();
  const transportStatus = useTransportStatus();
  const offline = transportStatus === "offline";
  const label = offline ? "OFFLINE" : "LIVE";

  return (
    <div className="min-h-screen bg-bh.bg text-bh.textMain font-sans relative overflow-hidden">
      {/* bunny watermark dead center, faint */}
      <div className="pointer-events-none select-none absolute inset-0 flex items-center justify-center">
        <div className="w-[600px] h-[600px] bg-bunny bg-contain bg-center bg-no-repeat opacity-[0.07]" />
      </div>

      {/* HUD row: timestamp left, BHABIT brand center, status cluster right */}
      <div className="relative z-10 flex flex-col items-center pt-4 px-4">
        <div className="w-full max-w-6xl flex items-start justify-between">
          {/* left timestamp pill */}
          <div className="flex">
            <div className="bg-bh.chipBg/80 border border-bh.borderGold rounded-full px-2 py-1 shadow-glowGold font-mono text-[10px] text-bh.textSoft leading-none">
              Latest: {tsLabel}
            </div>
          </div>

          {/* center neon brand */}
          <div className="text-center flex flex-col items-center">
            <div className="font-bhTitle font-bold text-transparent bg-clip-text bg-gradient-to-br from-bh.gold to-bh.goldDim text-[40px] leading-none drop-shadow-[0_0_8px_rgba(249,200,107,0.6)] tracking-tight">
              BHABIT
            </div>
            <div className="mt-2 font-bhTagline font-bold text-transparent bg-clip-text bg-gradient-to-br from-bh.purple via-bh.purpleDim to-bh.bg text-[24px] leading-none drop-shadow-[0_0_8px_rgba(162,75,255,0.7)] tracking-[0.35em]">
              PRØFITS  BÜ¥  IMPUL$€
            </div>
          </div>

          {/* right status cluster with useTransportStatus wiring */}
          <div className="flex items-center gap-2 text-[10px] text-bh.textSoft font-mono">
            {/* refresh button */}
            <button
              className="h-6 w-6 rounded-full bg-gradient-to-br from-bh.purple to-bh.purpleDim flex items-center justify-center text-[11px] text-bh.textMain font-bold shadow-glowPurple"
              onClick={() => {
                window.location.reload();
              }}
            >
              ↻
            </button>

            {/* tiny bar */}
            <div className="h-[6px] w-16 bg-bh.chipBg border border-bh.purple rounded-[3px] shadow-glowPurple relative">
              <div
                className={`absolute left-0 top-0 h-full rounded-[2px] transition-all duration-300 ease-in-out ${
                  offline ? "bg-bh.danger" : "bg-bh.purple"
                }`}
                style={{ width: offline ? "15%" : "90%" }}
              />
            </div>

            {/* status pill: LIVE (purple glow) or OFFLINE (red) */}
            <div
              className={`rounded-full px-2 py-[2px] leading-none text-[10px] font-bold uppercase ${
                offline
                  ? "bg-bh.danger text-bh.textMain"
                  : "bg-bh.chipBg border border-bh.purple text-bh.purple shadow-glowPurple"
              }`}
            >
              {label}
            </div>
          </div>
        </div>
      </div>

      {/* top headline row under header */}
      <div className="relative z-10 mt-6">
        <TopBannerScroll />
      </div>

      {/* HERO center block: 1-MIN GAINERS */}
      <main className="relative z-10 w-full max-w-4xl mx-auto px-4 mt-10 flex flex-col items-center text-center">
        <GainersTable1Min />

        {/* bottom row: 3-min gainers / losers side by side */}
        <div className="w-full max-w-5xl mx-auto grid grid-cols-1 md:grid-cols-2 gap-16 mt-16">
          <GainersTable3Min />
          <LosersTable3Min />
        </div>

        {/* volume / flow strip placeholder */}
        <VolumeBannerScroll />
      </main>

      {/* floating purple lightbulb in bottom-right */}
      <button
        className="fixed right-4 bottom-4 h-10 w-10 rounded-full bg-gradient-to-br from-bh.purple to-bh.purpleDim text-bh.textMain text-xl font-bold shadow-glowPurple flex items-center justify-center"
        onClick={() => {
          console.log("idea / assistant / help clicked");
        }}
        aria-label="Assistant"
      >
        💡
      </button>
    </div>
  );
}
