import { useEffect, useState } from "react";
import { getApiBaseUrl } from "../api.js";

/**
 * Chart-structure posture for the symbols on a board ("Bounce in 1h uptrend",
 * "Extended run · pullback risk", ...), from /api/structure-posture.
 *
 * Display context only. Nothing here filters, ranks or delays a row: a symbol
 * with no posture, or a failed request, simply shows no badge.
 */

const REFRESH_MS = 60_000; // the server caches each symbol for five minutes
const PENDING_MS = 6_000; // the server reads a few new symbols per call
const SETTLE_MS = 1_200; // boards reshuffle often; wait for the set to settle
const MAX_SYMBOLS = 24;

// symbol -> { posture, at }. Shared by every board on the page.
const cache = new Map();

export const normalizeSymbols = (symbols) => {
  const out = [];
  for (const raw of Array.isArray(symbols) ? symbols : []) {
    const sym = String(raw || "").trim().toUpperCase().replace(/-USD$/, "");
    if (/^[A-Z0-9]{1,15}$/.test(sym) && !out.includes(sym)) out.push(sym);
  }
  return out.slice(0, MAX_SYMBOLS).sort();
};

export function clearStructurePostureCache() {
  cache.clear();
}

export function useStructurePosture(symbols, { enabled = true } = {}) {
  const key = normalizeSymbols(symbols).join(",");
  const [, setVersion] = useState(0);

  useEffect(() => {
    if (!enabled || !key || typeof fetch !== "function") return undefined;
    const wanted = key.split(",");
    let cancelled = false;
    let timer = null;

    const load = async () => {
      let delay = REFRESH_MS;
      try {
        const res = await fetch(`${getApiBaseUrl()}/api/structure-posture?symbols=${encodeURIComponent(key)}`);
        const type = res.headers?.get?.("content-type") || "";
        if (res.ok && type.includes("application/json")) {
          const body = await res.json();
          const pending = new Set(Array.isArray(body?.pending) ? body.pending : []);
          const now = Date.now();
          for (const sym of wanted) {
            if (pending.has(sym)) continue;
            cache.set(sym, { posture: body?.postures?.[sym]?.posture || null, at: now });
          }
          if (pending.size) delay = PENDING_MS;
          if (!cancelled) setVersion((v) => v + 1);
        }
      } catch {
        // No badge is the correct fallback.
      }
      if (!cancelled) timer = setTimeout(load, delay);
    };

    const now = Date.now();
    const stale = wanted.some((sym) => !cache.has(sym) || now - cache.get(sym).at > REFRESH_MS);
    timer = setTimeout(load, stale ? SETTLE_MS : REFRESH_MS);
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [key, enabled]);

  const postures = {};
  for (const sym of key ? key.split(",") : []) {
    const hit = cache.get(sym);
    if (hit?.posture) postures[sym] = hit.posture;
  }
  return postures;
}

/** Posture for one row's token, or null. */
export function postureFor(postures, token) {
  const [sym] = normalizeSymbols([token?.symbol ?? token?.product_id]);
  return (sym && postures?.[sym]) || null;
}

export default useStructurePosture;
