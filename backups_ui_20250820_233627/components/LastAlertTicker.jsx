import React, { useMemo, useRef } from 'react';
import useSWR from 'swr';
import { API_ENDPOINTS, swrFetcher } from '../api.js';

const LastAlertTicker = () => {
  const pollMs = useMemo(() => {
    const v = Number(import.meta?.env?.VITE_ALERTS_POLL_MS);
    return Number.isFinite(v) && v >= 5000 ? v : 30000;
  }, []);
  const timerRef = useRef(null);

  // Use SWR to fetch last alert
  const url = (API_ENDPOINTS.alertsRecent || '/api/alerts/recent') + '?limit=1';
  const { data: res, error } = useSWR([url], swrFetcher, { refreshInterval: pollMs });
  const last = res?.alerts?.[res.alerts.length - 1] ?? null;

  if (!last) return null;

  return (
    <div className="w-full px-4 py-1 mb-2 rounded border border-gray-800 bg-black/40 text-[11px] text-gray-300 flex items-center gap-2">
      <span className="px-1 py-0.5 rounded bg-gray-700 text-white text-[10px]">ALERT</span>
      <span className="font-bold">{last.symbol}</span>
      <span className={`${last.direction==='up'?'text-green-300':'text-red-300'}`}>{last.direction==='up'?'↑':last.direction==='down'?'↓':'·'}</span>
      {typeof last.streak === 'number' && last.streak>0 && (
        <span className="px-1 py-0.5 rounded bg-blue-700/30 text-blue-200 text-[10px] leading-none">x{last.streak}</span>
      )}
      <span className="text-gray-400">score {Number(last.score||0).toFixed(2)}</span>
      <span className="ml-auto font-mono text-[10px] text-gray-500">{last.ts?.replace('T',' ')?.slice(0,19)}</span>
    </div>
  );
};

export default LastAlertTicker;
