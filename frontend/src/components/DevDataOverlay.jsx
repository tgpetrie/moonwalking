import React, { useEffect, useState } from 'react';
import { API_ENDPOINTS } from '../api.js';
import { fetchJson } from '../lib/api.js';

export default function DevDataOverlay() {
  const [samples, setSamples] = useState({});

  useEffect(() => {
    let mounted = true;
    const endpoints = {
      gainers1m: API_ENDPOINTS.gainersTable1Min,
      gainers3m: API_ENDPOINTS.gainersTable3Min,
      losers3m: API_ENDPOINTS.losersTable3Min,
      bottomBanner: API_ENDPOINTS.bottomBanner,
    };
    const run = async () => {
      const out = {};
      for (const [k, url] of Object.entries(endpoints)) {
        try {
          const res = await fetchJson(url);
          out[k] = {
            ok: true,
            count: Array.isArray(res?.data) ? res.data.length : (Array.isArray(res) ? res.length : 0),
            sample: (Array.isArray(res?.data) ? res.data[0] : Array.isArray(res) ? res[0] : res) || null,
          };
        } catch (e) {
          out[k] = { ok: false, error: String(e) };
        }
      }
      if (mounted) setSamples(out);
    };
    run();
    const id = setInterval(run, 8000);
    return () => { mounted = false; clearInterval(id); };
  }, []);

  if (!import.meta.env.DEV) return null;

  return (
    <div className="dev-overlay">
      <div className="dev-overlay-title">DEV: API Samples</div>
      {Object.keys(samples).length === 0 && (<div>loading…</div>)}
      {Object.entries(samples).map(([k,v]) => (
        <div key={k} className="dev-overlay-row">
          <div className="dev-overlay-row-title">{k} — {v?.ok ? `${v.count} rows` : 'ERR'}</div>
          <pre className="dev-overlay-pre">{v?.ok ? JSON.stringify(v.sample, null, 2) : v?.error}</pre>
        </div>
      ))}
    </div>
  );
}
