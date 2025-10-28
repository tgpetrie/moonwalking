import React from "react";
import { useHybridLive as useHybridLiveNamed } from "../hooks/useHybridLive";

export default function VolumeBannerScroll() {
  const { data = [] } = useHybridLiveNamed({
    endpoint: "/api/component/top-movers-bar",
    eventName: "vol1h",
    pollMs: 12000,
    initial: [],
  });

  return (
    <div className="text-center text-[11px] font-mono text-bh.textDim mt-8">
      {/* later we’ll render volume / flow chips from data */}
      {data.length ? "…" : "market flow coming soon…"}
    </div>
  );
}
