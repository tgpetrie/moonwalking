import React from 'react';

// tone: 'purple' (gainers) | 'pink' (losers)
export default function PeakBadge({ count = 0, tone = 'purple' }) {
  const toneClasses = tone === 'pink'
    ? 'bg-pink/30 text-pink-100'
    : 'bg-purple-900/40 text-purple-100';

  const base = 'px-1.5 py-[1px] rounded text-[10px] font-bold tracking-wide';

  if (!count || count <= 0) {
    return <span className={`${base} opacity-0 select-none`}>peak x0</span>;
  }
  return (
    <span className={`${base} ${toneClasses}`} title="Peak count (local max magnitude in window)">
      peak&nbsp;<span className="font-extrabold">x{count}</span>
    </span>
  );
}
