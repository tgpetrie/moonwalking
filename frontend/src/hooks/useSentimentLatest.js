import { useCallback, useEffect, useRef, useState } from "react";
import normalizeSentiment from "../adapters/normalizeSentiment";

/*
 * Stability fence: every consumer relies on this hook returning the same shape.
 * - Keep the last good snapshot alive even if the API blips.
 * - Never reintroduce SWR or expose half-normalized payloads directly in the UI.
 * - Treat all backend responses as snake_case and run them through normalizeSentiment.
 */

const FAIL_COOLDOWN_MS = 8000;
const REQUEST_TIMEOUT_MS = Number(import.meta.env.VITE_SENTIMENT_TIMEOUT_MS || 7000);

export function useSentimentLatest(
  symbol,
  { enabled = true, refreshMs = 30000 } = {}
) {
  // Use relative paths so Vite proxy handles the request
  // This avoids CORS issues by keeping requests same-origin
  const base = "";

  const lastGoodRef = useRef(null);
  const lastGoodSymbolRef = useRef(null);
  const [raw, setRaw] = useState(null);
  const [data, setData] = useState(() => normalizeSentiment(null));
  const [loading, setLoading] = useState(true);
  const [validating, setValidating] = useState(false);
  const [stale, setStale] = useState(false);
  const [error, setError] = useState(null);
  const [cooldownUntil, setCooldownUntil] = useState(0);

  const buildUrl = useCallback(() => {
    return symbol
      ? `${base}/api/sentiment/latest?symbol=${encodeURIComponent(symbol)}`
      : `${base}/api/sentiment/latest`;
  }, [base, symbol]);

  const fetchOnce = useCallback(async () => {
    if (!enabled) return;

    // Cooldown: if we failed recently, don't spam
    if (Date.now() < cooldownUntil) {
      return;
    }

    setValidating(true);
    setError(null);
    setStale(false);

    const ac = new AbortController();
    const timeoutId = setTimeout(() => ac.abort(), REQUEST_TIMEOUT_MS);
    try {
      const res = await fetch(buildUrl(), { cache: "no-store", signal: ac.signal });
      if (!res.ok) throw new Error(`sentiment ${res.status}`);

      const json = await res.json();
      lastGoodRef.current = json;
      lastGoodSymbolRef.current = symbol || "";
      setRaw(json);
      setData(normalizeSentiment(json));
      setLoading(false);
      setStale(false);
    } catch (err) {
      // Set cooldown on failure
      setCooldownUntil(Date.now() + FAIL_COOLDOWN_MS);

      const fallback = lastGoodRef.current;
      const fallbackSymbol = lastGoodSymbolRef.current;
      if (fallback && fallbackSymbol === (symbol || "")) {
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
      clearTimeout(timeoutId);
      setValidating(false);
    }
  }, [buildUrl, enabled, cooldownUntil, symbol]);

  useEffect(() => {
    if (!enabled) {
      return undefined;
    }

    fetchOnce();
    const id = setInterval(fetchOnce, refreshMs);
    return () => clearInterval(id);
  }, [fetchOnce, enabled, refreshMs]);

  useEffect(() => {
    lastGoodRef.current = null;
    lastGoodSymbolRef.current = symbol || "";
    setLoading(true);
    setError(null);
    setStale(false);
    setData(normalizeSentiment(null));
  }, [symbol]);

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
