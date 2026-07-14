import React from 'react';

// A tiny, lightweight legend explaining UI indicators and quick-read alert intent.
export default function IndicatorLegend({ onClose }) {
  return (
    <div className="mt-2 mb-4 w-full max-w-3xl mx-auto bg-black/60 border border-purple-900 rounded-xl p-3 text-xs text-white shadow-lg">
      <div className="flex items-start gap-3">
        <div className="flex-1 grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div className="flex items-center gap-2">
            <span className="px-1.5 py-0.5 rounded bg-emerald-700/30 text-emerald-200 text-[10px] leading-none font-semibold align-middle">BUY WATCH</span>
            <span className="text-white/80">Upside exists with support; still prefer pullback/retest over chasing.</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="px-1.5 py-0.5 rounded bg-yellow-700/30 text-yellow-200 text-[10px] leading-none font-semibold align-middle">RECONFIRM</span>
            <span className="text-white/80">Momentum is active but needs fresh volume, breadth, or rank hold.</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="px-1.5 py-0.5 rounded bg-purple-700/40 text-purple-200 text-[10px] leading-none font-semibold align-middle">NO CHASE</span>
            <span className="text-white/80">Fakeout, exhaustion, or weak context; wait for reclaim before buying.</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="px-1 py-0.5 rounded bg-blue-700/30 text-blue-200 text-[10px] leading-none font-semibold align-middle">x2</span>
            <span className="text-white/80">Consecutive ticks in same direction (streak). Larger x means longer run.</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="px-1.5 py-0.5 rounded bg-purple-700/40 text-purple-200 text-[10px] leading-none font-semibold align-middle">peak</span>
            <span className="text-white/80">Peak value used (held at local 1min high while conditions persist).</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="font-semibold text-emerald-custom">↑</span>
            <span className="text-white/80">Arrow size/color ≈ momentum score; green up/red down. Bigger/brighter = stronger.</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-blue font-bold">+3.2%</span>
            <span className="text-white/80">Blue = up moves; Pink = down moves. Prices use teal monospace.</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-white/80">Vol: —</span>
            <span className="text-white/60">A dash means the real 1h volume baseline is still warming.</span>
          </div>
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className="ml-2 shrink-0 px-2 py-1 rounded bg-purple-800/60 hover:bg-purple-700 text-white text-[11px] border border-purple-900"
            aria-label="Close legend"
          >
            Close
          </button>
        )}
      </div>
    </div>
  );
}
