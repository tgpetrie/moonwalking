import * as React from 'react';
import { useWatchlist } from '../hooks/useWatchlist.jsx';

export function WatchStar({ productId, size = 16, className = '', onToggled }) {
  const { list, toggle, saving } = useWatchlist();
  const active = Array.isArray(list) && productId ? list.includes(productId) : false;

  const onClick = async (e) => {
    e.preventDefault();
    e.stopPropagation();
    const prev = active;
    try { await toggle(productId); } catch {}
    try { if (typeof onToggled === 'function') onToggled(!prev, productId); } catch {}
  };

  return (
    <button
      aria-label={active ? 'Remove from watchlist' : 'Add to watchlist'}
      title={active ? 'Unstar' : 'Star'}
      onClick={onClick}
      className={`watch-star ${active ? 'is-active' : ''} ${className}`}
      disabled={saving}
      style={{ display: 'inline-flex', alignItems: 'center' }}
    >
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
           stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <polygon
          points="12 2 15 9 22 9 17 14 19 21 12 17 5 21 7 14 2 9 9 9"
          fill={active ? 'currentColor' : 'none'}
        />
      </svg>
    </button>
  );
}

export default WatchStar;
