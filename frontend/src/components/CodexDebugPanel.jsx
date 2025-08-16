import React from 'react';
import { useCodex } from '../context/CodexContext.jsx';

export default function CodexDebugPanel() {
  const { logs } = useCodex();
  return (
    <div className="bg-black/80 text-gray-200 p-3 rounded shadow max-h-96 overflow-y-auto text-xs font-mono">
      <div className="font-bold mb-2">Codex Debug</div>
      {logs.length === 0 && <div className="text-gray-500">No logs</div>}
      {logs.slice().reverse().map((l, idx) => (
        <div key={idx} className="mb-1">
          <span className="text-purple-400">{new Date(l.ts).toLocaleTimeString()}</span>{' '}
          <span className="text-teal-300">{l.symbol}</span>{' '}
          <span className="text-gray-400">{l.reason}</span>{' '}
          <span className="text-pink-300">{l.value}</span>
        </div>
      ))}
    </div>
  );
}
