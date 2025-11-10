import React from 'react';
import { FiRefreshCw } from 'react-icons/fi';

export default function ManualRefreshButton({ onAfterRefresh }) {
  return (
    <button
      onClick={() => { if (typeof onAfterRefresh === 'function') onAfterRefresh(); }}
      title="Refresh now"
      className="flex items-center gap-2 px-3 py-1 rounded bg-black/60 hover:bg-black/50 text-xs text-white border border-gray-700"
    >
      <FiRefreshCw />
      <span className="hidden sm:inline">Refresh</span>
    </button>
  );
}
