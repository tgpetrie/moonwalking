import React from "react";
import { useHybridLive as useHybridLiveNamed } from "../hooks/useHybridLive";

export default function TopBannerScroll() {
  const { data, source } = useHybridLiveNamed({
    endpoint: "/api/component/top-movers-bar",
    eventName: "banner1h",
    pollMs: 10000,
    initial: { data: [] },
  });

  return (
    <div className="w-full max-w-6xl mx-auto px-4 mt-4 flex flex-col md:flex-row md:justify-between md:items-start">
      <div className="text-[10px] font-mono leading-snug text-white tracking-[0.2em] uppercase">
        1H PRICE CHANGE • LIVE MARKET FEED
      </div>
    </div>
  );
}
