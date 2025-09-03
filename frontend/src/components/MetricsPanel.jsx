import React, { useEffect, useState } from 'react';
import { API_ENDPOINTS, fetchData } from '../api.js';
import CircuitBreakerBadge from './CircuitBreakerBadge.jsx';
import usePerformanceMonitor from '../hooks/usePerformanceMonitor.js';

export default function MetricsPanel({ refreshMs = 15000 }) {
  const [metrics, setMetrics] = useState(null);
  const [error, setError] = useState(null);
  
  // Performance monitoring
  const performance = usePerformanceMonitor('MetricsPanel', { enabled: process.env.NODE_ENV === 'development' });
  useEffect(() => {
    let mounted = true;
    let timer;
    const load = async () => {
      try {
        const data = await fetchData(API_ENDPOINTS.metrics + '?_t=' + Date.now());
        if (!mounted) return;
        setMetrics(data);
        setError(null);
      } catch (e) {
        if (!mounted) return;
        setError(e.message || 'error');
      }
      timer = setTimeout(load, refreshMs);
    };
    load();
    return () => { mounted = false; if (timer) clearTimeout(timer); };
  }, [refreshMs]);

  if (error && !metrics) {
    return <div className="text-xs text-red-400 font-mono">metrics: {error}</div>;
  }
  if (!metrics) {
    return <div className="text-xs text-gray-500 font-mono animate-pulse">metrics loading...</div>;
  }
  const pf = metrics.price_fetch || {};
  
  // Circuit breaker logic based on error metrics
  const circuitState = (metrics.errors_5xx > 5) ? 'open' : 
                      ((pf.rate_failures > 3) ? 'half-open' : 'closed');
  
  return (
    <div className="bg-black/50 border border-purple-800 rounded p-2 w-64 text-[10px] font-mono space-y-1">
      <div className="text-purple-300 font-semibold tracking-wide mb-2">METRICS</div>
      
      <CircuitBreakerBadge 
        state={circuitState} 
        failures={metrics.errors_5xx || 0}
        className="mb-2"
      />
      
      <div className="grid grid-cols-2 gap-x-2 gap-y-0.5">
        <LabelValue l="uptime" v={metrics.uptime_seconds + 's'} />
        <LabelValue l="5xx" v={metrics.errors_5xx} />
        <LabelValue l="pf.calls" v={pf.total_calls} />
        <LabelValue l="pf.cacheHit" v={pf.products_cache_hits} />
        <LabelValue l="pf.snapshot" v={pf.snapshot_served} />
        <LabelValue l="pf.failures" v={pf.rate_failures} />
        <LabelValue l="pf.dur" v={(pf.last_fetch_duration_ms||0).toFixed(1)+'ms'} />
        <LabelValue l="pf.snapshotAge" v={pf.snapshot_age_sec? pf.snapshot_age_sec.toFixed(1)+'s':'-'} />
      </div>
    </div>
  );
}

function LabelValue({ l, v }) {
  return (
    <div className="flex justify-between gap-2"><span className="text-gray-400">{l}</span><span className="text-gray-200 tabular-nums">{String(v)}</span></div>
  );
}