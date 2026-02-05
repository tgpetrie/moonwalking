import React from "react";
import { useHybridLive as useHybridLiveNamed } from "../hooks/useHybridLive";

function getPct(obj) {
  const cand =
    obj?.price_change_pct_1h ??
    obj?.price_change_percentage_1h ??
    obj?.pct_change_1h ??
    obj?.pct_change ??
    obj?.change_pct ??
    0;
  const n = Number(cand);
  if (Number.isNaN(n)) return 0;
  return n;
}

function formatPct(n) {
  const sign = n >= 0 ? "+" : "";
  return `${sign}${n.toFixed(2)}%`;
}

export default function TopBannerScroll() {
  const { data: payload = {} } = useHybridLiveNamed({
    endpoint: "/api/component/top-movers-bar",
    eventName: "banner1h",
    pollMs: 10000,
    initial: { data: [] },
  });

  const rows = Array.isArray(payload?.data) ? payload.data : [];

  return (
    <section className="w-full bg-black/0 text-white font-mono text-[11px] leading-tight px-4">
      <div className="w-full max-w-6xl mx-auto flex flex-col md:flex-row md:items-start md:justify-between">
        <div className="text-[11px] font-mono gain-text leading-snug flex items-center gap-2">
          <span className="font-semibold gain-text">1H PRICE CHANGE</span>
          <span className="text-white/40 font-normal">• LIVE MARKET FEED</span>
        </div>
      </div>

      <div className="mt-3 w-full max-w-6xl mx-auto overflow-x-auto whitespace-nowrap no-scrollbar">
        {rows.length === 0 ? (
          <div className="text-white/40 italic">loading…</div>
        ) : (
          rows.map((item, idx) => {
            const symRaw = item?.symbol || item?.ticker || "";
            const sym = symRaw.replace(/-USD$/i, "").toUpperCase();
            const pctNum = getPct(item || {});
            const pctStr = formatPct(pctNum);
            const isUp = pctNum >= 0;

            return (
              <span key={`${sym}-${idx}`} className={`inline-flex items-center ${isUp ? 'banner-chip banner-chip-gain' : 'banner-chip banner-chip-loss'} mr-2 mb-2`}>
                <span className="text-white text-[11px] font-semibold mr-2 tracking-wide">{sym || "--"}</span>
                <span className="text-[11px] font-semibold">{pctStr}</span>
              </span>
            );
          })
        )}
      </div>
    </section>
  );
}
