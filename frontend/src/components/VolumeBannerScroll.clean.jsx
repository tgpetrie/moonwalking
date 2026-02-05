import React from "react";
import { useHybridLive as useHybridLiveNamed } from "../hooks/useHybridLive";

function getVolMetric(obj) {
  const cand =
    obj?.volume_change_pct_1h ??
    obj?.vol_change_pct ??
    obj?.liquidity_change_pct ??
    obj?.volume_mult ??
    obj?.liquidity_mult ??
    obj?.flow_score ??
    null;

  if (cand == null) return null;
  const n = Number(cand);
  if (Number.isNaN(n)) return String(cand);

  if (n > 5) return `x${n.toFixed(1)}`;
  const sign = n >= 0 ? "+" : "";
  return `${sign}${n.toFixed(2)}%`;
}

export default function VolumeBannerScroll() {
  const { data: payload = {} } = useHybridLiveNamed({
    endpoint: "/api/component/top-movers-bar",
    eventName: "vol1h",
    pollMs: 12000,
    initial: { data: [] },
  });

  const rows = Array.isArray(payload?.data) ? payload.data : [];

  return (
    <section className="w-full bg-black/0 text-white font-mono text-[11px] leading-tight px-4 mt-8">
      <div className="w-full max-w-6xl mx-auto flex flex-col md:flex-row md:items-start md:justify-between">
        <div className="text-[11px] font-mono loss-text leading-snug flex items-center gap-2">
          <span className="font-semibold loss-text">1H VOLUME / FLOW</span>
          <span className="text-white/40 font-normal">• LIQUIDITY WATCH</span>
        </div>
      </div>

      <div className="mt-3 w-full max-w-6xl mx-auto overflow-x-auto whitespace-nowrap no-scrollbar">
        {rows.length === 0 ? (
          <div className="text-white/40 italic">loading flow…</div>
        ) : (
          rows.map((item, idx) => {
            const symRaw = item?.symbol || item?.ticker || "";
            const sym = symRaw.replace(/-USD$/i, "").toUpperCase();
            const metric = getVolMetric(item || {});
            const str = String(metric || '');
            const isPositive = str.startsWith('+') || str.startsWith('x');

            return (
              <span key={`${sym}-${idx}`} className={`inline-flex items-center ${isPositive ? 'banner-chip banner-chip-gain' : 'banner-chip banner-chip-loss'} mr-2 mb-2`}>
                <span className="text-white text-[11px] font-semibold mr-2 tracking-wide">{sym || "--"}</span>
                {metric ? (
                  <span className="text-[11px] font-semibold">{metric}</span>
                ) : (
                  <span className="text-[11px] font-semibold text-white/40">flow</span>
                )}
              </span>
            );
          })
        )}
      </div>
    </section>
  );
}
