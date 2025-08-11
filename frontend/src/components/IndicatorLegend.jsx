import React from 'react';

// A tiny, lightweight legend explaining UI indicators (streak x2, peak, arrows, colors)
export default function IndicatorLegend({ onClose }) {
  return (
    <div className="mt-2 mb-4 w-full max-w-2xl mx-auto bg-black/60 border border-purple-900 rounded-xl p-3 text-xs text-white shadow-lg">
      <div className="flex items-start gap-3">
        <div className="flex-1 grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div className="flex items-center gap-2">
            <span className="px-1 py-0.5 rounded bg-blue-700/30 text-blue-200 text-[10px] leading-none font-semibold align-middle">x2</span>
            <span className="text-white/80">Consecutive ticks in same direction (streak). Larger x means longer run.</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="px-1.5 py-0.5 rounded bg-purple-700/40 text-purple-200 text-[10px] leading-none font-semibold align-middle">peak</span>
            <span className="text-white/80">Peak value used (held at local 1min high while conditions persist).</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="font-semibold" style={{color:'#10B981'}}>↑</span>
            <span className="text-white/80">Arrow size/color ≈ momentum score; green up/red down. Bigger/brighter = stronger.</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-blue font-bold">+3.2%</span>
            <span className="text-white/80">Blue = up moves; Pink = down moves. Prices use teal monospace.</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-white/80">Vol: +4.1% <sup title="Estimated from price when 1h volume history is incomplete">≈</sup></span>
            <span className="text-white/60">≈ marks an estimated 1h volume change.</span>
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
