import { useEffect, useRef, useState, useLayoutEffect } from 'react';

export function usePerformanceMonitor(componentName, options = {}) {
  // Raise default threshold so we only warn on truly slow commits
  const { enabled = process.env.NODE_ENV === 'development', threshold = 120, sampleRate = 1 } = options;
  const startRef = useRef(0);
  const metricsRef = useRef({ totalRenders: 0, slowRenders: 0, lastRender: 0, maxRender: 0 });
  const [metrics, setMetrics] = useState({ totalRenders: 0, slowRenders: 0, lastRender: 0, maxRender: 0 });
  const warnRef = useRef(0);

  // Mark render start (runs every render)
  if (enabled) {
    startRef.current = performance.now();
  }

  // Measure at layout effect (closest to commit, avoids StrictMode double cleanup gap inflation)
  useLayoutEffect(() => {
    if (!enabled) return;
    const duration = performance.now() - startRef.current;
    const m = metricsRef.current;
    const newTotal = m.totalRenders + 1;
    const isSlow = duration > threshold;
    metricsRef.current = {
      totalRenders: newTotal,
      slowRenders: m.slowRenders + (isSlow ? 1 : 0),
      lastRender: duration,
      maxRender: Math.max(m.maxRender, duration)
    };

    // Throttle individual warnings (max one per 5s)
    const now = performance.now();
    if (isSlow && now - warnRef.current > 5000) {
      warnRef.current = now;
      console.warn(`🐌 Slow commit in ${componentName}: ${duration.toFixed(1)}ms (threshold ${threshold}ms)`);
    }

    // Sampled state update to reduce overhead
    if (newTotal % sampleRate === 0) {
      setMetrics({ ...metricsRef.current });
    }
  });

  // Periodic summary logging
  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    const loop = () => {
      if (cancelled) return;
      const m = metricsRef.current;
      // Only log summary if there has been at least one slow render or every ~2 minutes
      const shouldLog = m.slowRenders > 0 || (m.totalRenders % 120 === 0);
      if (shouldLog && m.totalRenders) {
        const pct = ((m.slowRenders / m.totalRenders) * 100).toFixed(1);
        console.log(`📊 ${componentName} perf: last=${m.lastRender.toFixed(1)}ms max=${m.maxRender.toFixed(1)}ms slow%=${pct}% total=${m.totalRenders}`);
      }
      // Jitter next tick between 20s-30s to avoid sync spam across many components
      const next = 20000 + Math.random()*10000;
      setTimeout(loop, next);
    };
    const t = setTimeout(loop, 25000); // initial delay
    return () => { cancelled = true; clearTimeout(t); };
  }, [enabled, componentName]);

  return { metrics };
}

export default usePerformanceMonitor;