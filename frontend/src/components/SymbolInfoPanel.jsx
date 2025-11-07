import React, { useState } from "react";

export default function SymbolInfoPanel({ symbol, details, onClose }) {
  if (!symbol) return null;

  const [tab, setTab] = useState("Info");
  const tabs = ["Info", "Volume", "Trend"];

  return (
    <div className="fixed bottom-6 right-6 z-40 w-[320px] rounded-2xl border border-[#a16dff50] bg-black/80 p-4 text-white shadow-[0_0_24px_rgba(161,109,255,0.25)] backdrop-blur-sm">
      <div className="flex items-start justify-between">
        <h3 className="mb-2 font-bold text-[#a16dff] text-lg">{symbol}</h3>
        <button
          type="button"
          aria-label="Close symbol info"
          onClick={onClose}
          className="ml-3 text-white/60 hover:text-white"
        >
          ×
        </button>
      </div>

      <div className="mb-3 flex gap-3">
        {tabs.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-2 py-1 text-xs rounded transition-colors ${
              tab === t ? "text-[#a16dff]" : "text-white/70 hover:text-[#ff7a1a]"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      <div className="text-sm text-gray-300">
        {tab === "Info" &&
          (details ? (
            <p>{details}</p>
          ) : (
            <p className="italic text-gray-500">No data yet</p>
          ))}
        {tab === "Volume" && (
          <p className="italic text-gray-500">Volume detail placeholder</p>
        )}
        {tab === "Trend" && (
          <p className="italic text-gray-500">Trend placeholder</p>
        )}
      </div>
    </div>
  );
}
