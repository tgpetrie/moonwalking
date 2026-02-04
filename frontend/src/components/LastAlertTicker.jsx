import React, { useEffect, useMemo, useRef, useState } from 'react';
import { API_ENDPOINTS, fetchData } from '../api.js';
import { deriveAlertType, labelFromTypeKey } from '../utils/alertClassifier.js';

const fmtPct = (p) => {
  if (p == null || Number.isNaN(Number(p))) return null;
  const n = Number(p);
  const sign = n > 0 ? '+' : '';
  return `${sign}${n.toFixed(2)}%`;
};

const fmtTime = (ms) => {
  if (!Number.isFinite(ms)) return '—';
  const d = new Date(ms);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toISOString().replace('T', ' ').slice(0, 19);
};

const LastAlertTicker = () => {
  const [last, setLast] = useState(null);
  const [error, setError] = useState(null);
  const pollMs = useMemo(() => {
    const v = Number(import.meta?.env?.VITE_ALERTS_POLL_MS);
    return Number.isFinite(v) && v >= 5000 ? v : 30000;
  }, []);
  const timerRef = useRef(null);

  useEffect(() => {
    let mounted = true;
    const poll = async () => {
      try {
        const res = await fetchData((API_ENDPOINTS.alertsRecent || '/api/alerts/recent') + '?limit=1');
        if (!mounted) return;
        if (res && Array.isArray(res.alerts) && res.alerts.length) {
          setLast(res.alerts[res.alerts.length - 1]);
          setError(null);
        }
      } catch (e) {
        if (!mounted) return;
        setError('alerts offline');
      } finally {
        timerRef.current = setTimeout(poll, pollMs);
      }
    };
    poll();
    return () => {
      mounted = false;
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [pollMs]);

  if (!last) return null;

  const label = last?.type_key
    ? labelFromTypeKey(last.type_key)
    : deriveAlertType({ type: last?.type, pct: last?.pct, severity: last?.severity });
  const pctText = fmtPct(last?.pct);
  const w = last?.window || '3m';
  const severity = String(last?.severity || 'info').toUpperCase();
  const tsMs = Number(last?.ts_ms ?? last?.tsMs ?? Date.parse(last?.ts || ''));
  const pctTone = Number(last?.pct) >= 0 ? 'text-green-300' : 'text-red-300';

  return (
    <div className="w-full px-4 py-1 mb-2 rounded border border-gray-800 bg-black/40 text-[11px] text-gray-300 flex items-center gap-2">
      <span className="px-1 py-0.5 rounded bg-gray-700 text-white text-[10px]">{label}</span>
      <span className="font-bold">{last.symbol}</span>
      {pctText && <span className={pctTone}>{pctText}</span>}
      <span className="text-gray-400">{w}</span>
      <span className="ml-auto px-1 py-0.5 rounded bg-gray-700 text-[10px]">{severity}</span>
      <span className="font-mono text-[10px] text-gray-500">{fmtTime(tsMs)}</span>
    </div>
  );
};

export default LastAlertTicker;
