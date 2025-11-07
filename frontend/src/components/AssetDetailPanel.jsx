import React, { useState } from "react";

export default function AssetDetailPanel({ symbol, sentimentData, marketData, onClose }) {
  const [tab, setTab] = useState("overview");
  if (!symbol) return null;

  const s = sentimentData?.[symbol] || null;
  const m = marketData?.[symbol] || null;

  return (
    <div className="fixed top-16 right-6 w-[360px] bg-black/90 border border-white/10 rounded-lg shadow-2xl backdrop-blur z-50 text-white">
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/5">
        <div className="text-[13px] font-semibold tracking-wide">{symbol}</div>
        <button onClick={onClose} className="text-white/50 hover:text-white text-[12px]">×</button>
      </div>

      <div className="flex gap-2 px-4 py-2 border-b border-white/5 text-[11px] uppercase tracking-wide">
        <button onClick={() => setTab("overview")} className={tab === "overview" ? "text-[#f9c86b]" : "text-white/40"}>Overview</button>
        <button onClick={() => setTab("sentiment")} className={tab === "sentiment" ? "text-[#f9c86b]" : "text-white/40"}>Sentiment</button>
        <button onClick={() => setTab("chart")} className={tab === "chart" ? "text-[#f9c86b]" : "text-white/40"}>Chart</button>
      </div>

      <div className="p-4 text-[12px] space-y-3">
        {tab === "overview" && (
          <div>
            <div className="text-white/60 text-[11px]">Latest</div>
            <div className="flex items-baseline gap-2">
              <div className="text-[20px] font-semibold leading-none">
                {m?.currentPrice != null ? `$${m.currentPrice}` : "--"}
              </div>
              <div className={m?.changePct1m > 0 ? "text-[#f9c86b]" : "text-[#a24bff]"}>
                {m?.changePct1m != null ? `${m.changePct1m.toFixed(2)}%` : ""}
              </div>
            </div>
            {m?.ts && <div className="text-[10px] text-white/30">as of {m.ts}</div>}
          </div>
        )}

        {tab === "sentiment" && (
          <div>
            <div className="text-white/60 text-[11px]">Sentiment</div>
            {s ? (
              <>
                <div className="flex items-center gap-2">
                  <span className="px-2 py-1 rounded bg-white/5 text-[10px] uppercase tracking-wide">{s.sentiment}</span>
                  <span className="text-[10px] text-white/50">score {Math.round(s.score * 100) / 100}</span>
                </div>
                {s.sources?.length ? (
                  <ul className="text-[11px] text-white/50 list-disc list-inside space-y-1 max-h-[110px] overflow-auto">
                    {s.sources.map((src, i) => (
                      <li key={i}>{src}</li>
                    ))}
                  </ul>
                ) : (
                  <div className="text-white/30 text-[11px]">No source details.</div>
                )}
              </>
            ) : (
              <div className="text-white/30 text-[11px]">No sentiment for this symbol.</div>
            )}
          </div>
        )}

        {tab === "chart" && (
          <div className="text-white/30 text-[11px]">
            Chart placeholder — wire to your price history endpoint.
          </div>
        )}
      </div>
    </div>
  );
}

