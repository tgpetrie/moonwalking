import React from 'react';
import { useWebSocket } from '../context/websocketcontext.jsx';
import { getApiBaseUrl } from '../api.js';

export default function DataFlowTest() {
  const debugEnabled = React.useMemo(() => {
    try {
      return typeof window !== 'undefined' && window.location.search.includes('debug');
    } catch (_) {
      return false;
    }
  }, []);

  const wsData = useWebSocket();

  if (!debugEnabled) {
    return null;
  }

  const apiBaseUrl = getApiBaseUrl();

  return (
    <div className="fixed top-2 left-2 z-[9998] bg-red-900/90 text-white text-xs p-2 rounded max-w-sm max-h-40 overflow-y-auto">
      <div className="font-bold mb-1">Data Flow Debug</div>
      <div>API Base: {apiBaseUrl}</div>
      <div>WS Connected: {wsData?.isConnected ? 'Yes' : 'No'}</div>
      <div>WS Polling: {wsData?.isPolling ? 'Yes' : 'No'}</div>
      <div>WS Data Items: {wsData?.latestData?.crypto?.length || 0}</div>
      {wsData?.error && <div className="text-red-300">Error: {wsData.error}</div>}
    </div>
  );
}
