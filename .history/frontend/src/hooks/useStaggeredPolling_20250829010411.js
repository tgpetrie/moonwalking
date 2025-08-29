// A hook providing staggered polling with optional jitter so multiple tables don't refetch simultaneously.
import { useEffect, useRef, useState } from 'react';

/**
 * useStaggeredPolling
 * @param {Function} fetcher async () => data
 * @param {number} interval base interval ms
 * @param {number} offset initial offset ms before first poll
 * @param {number} jitter random jitter range in ms (uniform 0..jitter each cycle)
 * @param {boolean} active enable/disable polling
 * @returns {Object} { data, error, loading, lastUpdated, refresh }
 */
export function useStaggeredPolling(fetcher, { interval, offset = 0, jitter = 0, active = true }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState(null);
  const timerRef = useRef(null);
  const mountedRef = useRef(false);

  const run = async () => {
    if (!active) return;
    try {
      setLoading(prev => (data == null && prev === true ? true : false));
      const result = await fetcher();
      setData(result);
      setError(null);
      setLastUpdated(Date.now());
    } catch (e) {
      setError(e);
    } finally {
      setLoading(false);
    }
  };

  const schedule = (first = false) => {
    if (!active) return;
    const base = interval || 30000;
    const extra = jitter ? Math.floor(Math.random() * jitter) : 0;
    const delay = first ? offset + extra : base + extra;
    timerRef.current = setTimeout(async () => {
      await run();
      schedule(false);
    }, delay);
  };

  useEffect(() => {
    mountedRef.current = true;
    schedule(true);
    return () => {
      mountedRef.current = false;
      if (timerRef.current) clearTimeout(timerRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [interval, offset, jitter, active]);

  const refresh = () => {
    if (timerRef.current) clearTimeout(timerRef.current);
    run().then(() => schedule(false));
  };

  return { data, error, loading, lastUpdated, refresh };
}
