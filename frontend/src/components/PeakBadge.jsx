import React from 'react';

// tone: 'purple' (gainers) | 'pink' (losers)
export default function PeakBadge({ count = 0, tone = 'purple' }) {
  const toneClasses = tone === 'pink'
  ? 'bg-pink/30 text-pink-100'
  : 'bg-purple-900/40 text-purple-100';

  const base = 'px-2 py-[2px] rounded text-[11px] font-bold tracking-wide inline-block';

  if (!count || count <= 0) {
    return <span className={`${base} opacity-0 select-none`} aria-hidden> </span>;
  }
  const label = count <= 1 ? 'x' : `x${count}`;
  return (
    <span className={`${base} ${toneClasses} badge-peak`} title="Peak count (local max magnitude in window)">
      {label}
    </span>
  );
}
