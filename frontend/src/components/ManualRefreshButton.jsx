import React, { useState } from 'react';
import { FiRefreshCw } from 'react-icons/fi';
import { useWebSocket } from '../context/websocketcontext.jsx';

export default function ManualRefreshButton({ onAfterRefresh }) {
  const { refreshNow } = useWebSocket();
  const [busy, setBusy] = useState(false);

  const click = async () => {
    if (busy) return;
    setBusy(true);
    try {
      await refreshNow();
    } finally {
      setBusy(false);
      onAfterRefresh && onAfterRefresh();
    }
  };

  return (
    <button
      onClick={click}
      className={
        'w-10 h-10 rounded-full flex items-center justify-center bg-gradient-to-r from-purple-600 to-purple-900 text-white shadow-lg transform transition-all duration-300 focus:outline-none focus:ring-2 focus:ring-purple-400 ' +
        (busy ? 'opacity-70 cursor-wait' : 'hover:scale-110 hover:shadow-[0_0_25px_rgba(168,85,247,0.6)]')
      }
      aria-label="Refresh"
      title="Refresh"
      disabled={busy}
    >
      <FiRefreshCw className={'text-xl text-purple-300 ' + (busy ? 'animate-spin' : '')} />
    </button>
  );
}

