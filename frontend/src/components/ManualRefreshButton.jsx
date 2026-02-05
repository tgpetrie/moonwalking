import React from 'react';
import { FiRefreshCw } from 'react-icons/fi';

// Minimal ManualRefreshButton used during UI restore/build.
// Calls onAfterRefresh if provided.
export default function ManualRefreshButton({ onAfterRefresh }) {
  const handleClick = () => {
    if (typeof onAfterRefresh === 'function') onAfterRefresh();
  };

  return (
    <button
      onClick={handleClick}
      className="p-2 rounded-full bg-black/40 hover:bg-black/30 border border-gray-700 text-xs text-white"
      title="Refresh"
      aria-label="Refresh"
    >
      <FiRefreshCw />
    </button>
  );
}
