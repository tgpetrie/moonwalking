import React, { useState } from 'react';
import PropTypes from 'prop-types';
import { FiStar, FiStar as StarIcon } from 'react-icons/fi';

// Minimal, test-safe WatchStar component used across mover rows.
// Keeps internal toggled state and calls onToggled when present.
export default function WatchStar({ productId, price, onToggled }) {
  const [active, setActive] = useState(false);

  const handleClick = (e) => {
    e.preventDefault();
    e.stopPropagation();
    const next = !active;
    setActive(next);
    if (typeof onToggled === 'function') {
      try { onToggled(productId, next); } catch (_) { /* swallow */ }
    }
  };

  return (
    <button
      type="button"
      aria-pressed={active}
      aria-label={active ? 'Remove from watchlist' : 'Add to watchlist'}
      onClick={handleClick}
      className={`inline-flex items-center justify-center w-6 h-6 rounded focus:outline-none transition ${active ? 'text-yellow-400' : 'text-gray-400'}`}
    >
      <StarIcon className="w-4 h-4" />
    </button>
  );
}

WatchStar.propTypes = {
  productId: PropTypes.string,
  price: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
  onToggled: PropTypes.func,
};
