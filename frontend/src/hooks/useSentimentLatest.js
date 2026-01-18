import { useCallback, useEffect, useRef, useState } from "react";
import normalizeSentiment from "../adapters/normalizeSentiment";
import { getSentimentBaseUrl } from "../api";

/*
 * Stability fence: every consumer relies on this hook returning the same shape.
 * - Keep the last good snapshot alive even if the API blips.
 * - Never reintroduce SWR or expose half-normalized payloads directly in the UI.
 * - Treat all backend responses as snake_case and run them through normalizeSentiment.
 */

const FAIL_COOLDOWN_MS = 8000;
const REQUEST_TIMEOUT_MS = Number(import.meta.env.VITE_SENTIMENT_TIMEOUT_MS || 7000);
const LAST_GOOD_KEY = "mw_last_good_sentiment";
const LAST_GOOD_AT_KEY = "mw_last_good_sentiment_at";

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

const readCachedAt = () => {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(LAST_GOOD_AT_KEY);
    const n = Number(raw);
    return Number.isFinite(n) ? n : null;
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
  const base = (getSentimentBaseUrl() || "").replace(/\/$/, "");
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

  const buildUrl = useCallback(() => {
    const path = symbol
      ? `/api/sentiment/latest?symbol=${encodeURIComponent(symbol)}`
      : "/api/sentiment/latest";
    return base ? `${base}${path}` : path;
  }, [base, symbol]);

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
      setData(normalizeSentiment(json));
      setLoading(false);
      setStale(false);
    } catch (err) {
      setCooldownUntil(Date.now() + FAIL_COOLDOWN_MS);
      const fallback = lastGoodRef.current;
      const fallbackSymbol = lastGoodSymbolRef.current;
      if (fallback && fallbackSymbol === (symbol || "")) {
        setRaw(fallback);
        setData(normalizeSentiment(fallback));
        setError(null);
        setStale(true);
      } else {
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
