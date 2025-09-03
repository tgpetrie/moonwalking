import { useState, useEffect, useCallback } from 'react';

/**
 * A custom hook to fetch data from an endpoint and poll for updates.
 * @param {string} endpoint - The API endpoint to fetch from.
 * @param {object} [options={}] - Configuration options.
 * @param {number} [options.interval=15000] - The polling interval in milliseconds. Set to null to disable polling.
 * @param {boolean} [options.auto=true] - Whether to automatically poll.
 * @returns {{data: any, loading: boolean, error: string|null, refresh: function}}
 */
const usePollingFetch = (endpoint, options = {}) => {
  const { interval = 15000, auto = true } = options;

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  const refresh = useCallback(() => {
    setRefreshTrigger(c => c + 1);
  }, []);

  useEffect(() => {
    const controller = new AbortController();

    const doFetch = async (isPoll = false) => {
      // Only show loading state on initial fetch or manual refresh, not on background polls.
      if (!isPoll) {
        setLoading(true);
      }
      setError(null);

      try {
        const res = await fetch(endpoint, { signal: controller.signal });
        if (!res.ok) throw new Error(`HTTP error ${res.status}`);
        const jsonData = await res.json();
        if (!controller.signal.aborted) {
          setData(jsonData);
        }
      } catch (e) {
        if (e.name !== 'AbortError') {
          setError(e.message);
        }
      } finally {
        if (!controller.signal.aborted && !isPoll) {
          setLoading(false);
        }
      }
    };

    doFetch(false);
    const intervalId = auto && interval ? setInterval(() => doFetch(true), interval) : null;

    return () => {
      controller.abort();
      if (intervalId) clearInterval(intervalId);
    };
  }, [endpoint, interval, auto, refreshTrigger]);

  return { data, loading, error, refresh };
};

export default usePollingFetch;