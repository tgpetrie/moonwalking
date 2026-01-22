import { useCallback, useEffect, useRef, useState } from "react";
import normalizeSentiment from "../adapters/normalizeSentiment";

/*
 * Stability fence: every consumer relies on this hook returning the same shape.
 * - Keep the last good snapshot alive even if the API blips.
 * - Never reintroduce SWR or expose half-normalized payloads directly in the UI.
 * - Treat all backend responses as snake_case and run them through normalizeSentiment.
 * - Respect sentiment_meta contract: ok, pipelineRunning, staleSeconds, lastOkTs, lastTryTs, error
 * - Compute pipelineStatus: "LIVE" | "STALE" | "OFFLINE"
 */

const FAIL_COOLDOWN_MS = 8000;
const REQUEST_TIMEOUT_MS = Number(import.meta.env.VITE_SENTIMENT_TIMEOUT_MS || 7000);
const LAST_GOOD_KEY = "mw_last_good_sentiment";
const LAST_GOOD_AT_KEY = "mw_last_good_sentiment_at";
// pipelineStatus computation lives in normalizeSentiment.js (single source of truth)

const parsePipelineResponse = async (response) => {
  let payload = null;
  try {
    payload = await response.json();
  } catch (err) {
    payload = null;
  }
  if (!response.ok) {
    const detail =
      payload?.detail ?? payload?.error ?? payload?.message ?? response.statusText ?? `HTTP ${response.status}`;
    throw new Error(detail);
  }
  return payload;
};

const readCached = () => {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(LAST_GOOD_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
};

const writeCached = (payload) => {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(LAST_GOOD_KEY, JSON.stringify(payload));
    window.localStorage.setItem(LAST_GOOD_AT_KEY, String(Date.now()));
  } catch {}
};

export function useSentimentLatest(
  symbol,
  { enabled = true, refreshMs = 30000 } = {}
) {
  const cached = readCached();
  const cachedNorm = normalizeSentiment(cached);

  const lastGoodRef = useRef(cached || null);
  const lastGoodSymbolRef = useRef(null);
  const [raw, setRaw] = useState(cached || null);
  const [data, setData] = useState(() => cachedNorm);
  const [loading, setLoading] = useState(() => !cached);
  const [validating, setValidating] = useState(false);
  const [stale, setStale] = useState(() => Boolean(cached));
  const [error, setError] = useState(null);
  const [cooldownUntil, setCooldownUntil] = useState(0);
  // pipelineStatus is computed inside normalizeSentiment.js; hook will expose it from normalized data

  // Use relative paths only - Vite proxy handles routing to backend
  const buildUrl = useCallback(() => {
    const path = symbol
      ? `/api/sentiment/latest?symbol=${encodeURIComponent(symbol)}`
      : "/api/sentiment/latest";
    return path;
  }, [symbol]);

  const fetchOnce = useCallback(async () => {
    if (!enabled) return;

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
      const json = await parsePipelineResponse(res);

      lastGoodRef.current = json;
      lastGoodSymbolRef.current = symbol || "";
      writeCached(json);
      setRaw(json);
      const norm = normalizeSentiment(json);
      setData(norm);
      setLoading(false);
      setStale(norm.pipelineStatus === "STALE");
    } catch (err) {
      setCooldownUntil(Date.now() + FAIL_COOLDOWN_MS);
      const fallback = lastGoodRef.current;
      const fallbackSymbol = lastGoodSymbolRef.current;
      if (fallback && fallbackSymbol === (symbol || "")) {
        setRaw(fallback);
        const norm = normalizeSentiment(fallback);
        setData(norm);
        setError(null);
        setStale(true);
        // keep pipelineStatus coming from normalized fallback
      } else {
        setError(err);
        // no data and fetch failed => OFFLINE semantic will be derived by consumers from data==null
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
    // New sentiment_meta contract fields (delegated to normalizeSentiment)
    sentimentMeta: data?.sentimentMeta ?? null,
    pipelineStatus: data?.pipelineStatus ?? (cached ? "STALE" : "OFFLINE"), // "LIVE" | "STALE" | "OFFLINE"
  };
}

export default useSentimentLatest;
