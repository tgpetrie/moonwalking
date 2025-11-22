import { useCallback, useEffect, useRef, useState } from "react";
import normalizeSentiment from "../adapters/normalizeSentiment";

/*
 * Stability fence: every consumer relies on this hook returning the same shape.
 * - Keep the last good snapshot alive even if the API blips.
 * - Never reintroduce SWR or expose half-normalized payloads directly in the UI.
 * - Treat all backend responses as snake_case and run them through normalizeSentiment.
 */

const DEFAULT_BASE = "http://127.0.0.1:8001";

export function useSentimentLatest(
  symbol,
  { enabled = true, refreshMs = 30000 } = {}
) {
  const baseRaw = import.meta.env.VITE_SENTIMENT_API_BASE || DEFAULT_BASE;
  const base = baseRaw.replace(/\/$/, "");

  const lastGoodRef = useRef(null);
  const [raw, setRaw] = useState(null);
  const [data, setData] = useState(() => normalizeSentiment(null));
  const [loading, setLoading] = useState(true);
  const [validating, setValidating] = useState(false);
  const [stale, setStale] = useState(false);
  const [error, setError] = useState(null);

  const buildUrl = useCallback(() => {
    return symbol
      ? `${base}/sentiment/latest?symbol=${encodeURIComponent(symbol)}`
      : `${base}/sentiment/latest`;
  }, [base, symbol]);

  const fetchOnce = useCallback(async () => {
    if (!enabled) return;

    setValidating(true);
    setError(null);
    setStale(false);

    try {
      const res = await fetch(buildUrl(), { cache: "no-store" });
      if (!res.ok) throw new Error(`sentiment ${res.status}`);

      const json = await res.json();
      lastGoodRef.current = json;
      setRaw(json);
      setData(normalizeSentiment(json));
      setLoading(false);
      setStale(false);
    } catch (err) {
      const fallback = lastGoodRef.current;
      if (fallback) {
        setRaw(fallback);
        setData(normalizeSentiment(fallback));
        setError(null);
        setStale(true);
      }
      if (!fallback) {
        setError(err);
      }
      setLoading(false);
    } finally {
      setValidating(false);
    }
  }, [buildUrl, enabled]);

  useEffect(() => {
    if (!enabled) {
      return undefined;
    }

    fetchOnce();
    const id = setInterval(fetchOnce, refreshMs);
    return () => clearInterval(id);
  }, [fetchOnce, enabled, refreshMs]);

  return {
    data,
    raw,
    loading,
    validating,
    stale,
    error,
    refresh: fetchOnce,
  };
}

export default useSentimentLatest;
