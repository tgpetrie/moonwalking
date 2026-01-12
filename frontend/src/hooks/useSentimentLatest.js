import { useCallback, useEffect, useRef, useState } from "react";
import normalizeSentiment from "../adapters/normalizeSentiment";
import { getSentimentBaseUrl, getApiBaseUrl } from "../api";

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
  const apiBase = (getApiBaseUrl() || "").replace(/\/$/, "");

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

  const fetchProxySentiment = useCallback(async () => {
    const resolvedBase = (apiBase || base || "http://127.0.0.1:5003").replace(/\/$/, "");
    const fetchOne = async (path) => {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
      try {
        const res = await fetch(`${resolvedBase}${path}`, { cache: "no-store", signal: controller.signal });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      } finally {
        clearTimeout(timeoutId);
      }
    };
    try {
      const [fngRes, marketRes] = await Promise.allSettled([
        fetchOne("/api/sentiment/fng"),
        fetchOne("/api/sentiment/market"),
      ]);
      return {
        fng: fngRes.status === "fulfilled" ? fngRes.value : null,
        market: marketRes.status === "fulfilled" ? marketRes.value : null,
      };
    } catch (err) {
      if (import.meta.env.DEV) {
        console.warn("[useSentimentLatest] proxy sentiment failed", err?.message || err);
      }
      return null;
    }
  }, [apiBase, base]);

  const fetchOnce = useCallback(async () => {
    if (!enabled) return;

    if (Date.now() < cooldownUntil) {
      return;
    }

    setValidating(true);
    setError(null);
    setStale(false);

    const proxyPromise = fetchProxySentiment();
    const ac = new AbortController();
    const timeoutId = setTimeout(() => ac.abort(), REQUEST_TIMEOUT_MS);
    try {
      const res = await fetch(buildUrl(), { cache: "no-store", signal: ac.signal });
      const json = await parsePipelineResponse(res);
      const proxies = await proxyPromise.catch(() => null);
      const mergedRaw = {
        ...json,
        fear_greed: json?.fear_greed ?? json?.fearGreed ?? proxies?.fng,
        market_pulse: json?.market_pulse ?? json?.marketPulse ?? proxies?.market,
      };
      lastGoodRef.current = mergedRaw;
      lastGoodSymbolRef.current = symbol || "";
      writeCached(mergedRaw);
      setRaw(mergedRaw);
      setData(normalizeSentiment(mergedRaw));
      setLoading(false);
      setStale(false);
    } catch (err) {
      setCooldownUntil(Date.now() + FAIL_COOLDOWN_MS);

      const proxies = await proxyPromise.catch(() => null);
      const fallback = lastGoodRef.current;
      const fallbackSymbol = lastGoodSymbolRef.current;

      if (proxies && (proxies.fng || proxies.market)) {
        const mergedRaw = { fear_greed: proxies.fng, market_pulse: proxies.market };
        lastGoodRef.current = mergedRaw;
        lastGoodSymbolRef.current = symbol || "";
        writeCached(mergedRaw);
        setRaw(mergedRaw);
        setData(normalizeSentiment(mergedRaw));
        setError(null);
        setStale(Boolean(proxies.fng?.stale || proxies.market?.stale));
      } else if (fallback && fallbackSymbol === (symbol || "")) {
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
  }, [buildUrl, enabled, cooldownUntil, symbol, fetchProxySentiment]);

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
